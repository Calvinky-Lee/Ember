"""Store API (spec 06) — the persistence contract P3 writes and P4 reads.

What these pin down (and why):
- `seq` is a monotonic per-run cursor and `get_run_events(after_seq=N)` returns
  exactly the tail, ordered — the guarantee `ember race` incremental polling relies
  on and that replays reproduce original order.
- `completed_tuples` marks a (task, arm, k) unit done once its answer row exists —
  the harness's zero-duplicate resume key (spec 05 acceptance).
- Totals count every call, overhead included (D4), and surface escalation counts.
- Reports and runs survive a fresh engine (process restart) → offline replay works.
"""
import threading

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend.db import models, store


@pytest.fixture
def db(monkeypatch, tmp_path):
    """A throwaway file-backed store, same pragmas as prod, isolated per test.
    File-backed (not :memory:) so the restart test can rebind a new engine to it."""
    db_file = tmp_path / "ember.sqlite"

    def make_engine():
        eng = create_engine(f"sqlite:///{db_file}",
                            connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(eng, "connect")
        def _pragmas(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        return eng

    monkeypatch.setattr(store, "engine", make_engine())
    store.init_db()
    return {"file": db_file, "rebind": lambda: monkeypatch.setattr(store, "engine", make_engine())}


def _impact(**kw):
    base = {"model_key": "test:model", "tokens_in": 100, "tokens_out": 50,
            "wh": 0.03, "gco2": 0.011, "cost_usd": 0.0011, "zone": "SE",
            "gco2_per_kwh": 25.0, "intensity_label": "live", "energy_label": "estimated"}
    base.update(kw)
    return base


def test_seq_is_monotonic_per_run(db):
    """Each run's seq starts at 1 and increments by 1 — the cursor race polling and
    ordered replay both depend on it. Two runs number independently."""
    r = store.create_run("run-A")
    s1 = store.record_call(r, "t1", "a", 0, "answer", _impact())
    s2 = store.record_call(r, "t2", "b", 0, "answer", _impact())
    s3 = store.record_call(r, "t3", "a", 0, "answer", _impact())
    assert [s1, s2, s3] == [1, 2, 3]
    other = store.create_run("run-B")
    assert store.record_call(other, "t1", "a", 0, "answer", _impact()) == 1


def test_get_run_events_returns_exact_ordered_tail(db):
    """after_seq=N returns exactly the events with seq > N, in order — no earlier
    rows, no gaps. This is the whole incremental-read contract."""
    r = store.create_run("run-1")
    for i in range(5):
        store.record_call(r, f"t{i}", "a", 0, "answer", _impact())
    tail = store.get_run_events(r, after_seq=3)
    assert [e["seq"] for e in tail] == [4, 5]
    assert store.get_run_events(r, after_seq=5) == []
    assert [e["seq"] for e in store.get_run_events(r)] == [1, 2, 3, 4, 5]


def test_event_dict_has_frozen_contract_keys(db):
    """The h8-frozen shape P4 renders. Missing/renamed keys break the race view —
    guard the exact contract keys from spec 06."""
    r = store.create_run("run-1")
    store.record_call(r, "gsm8k-017", "b", 0, "answer",
                      _impact(gco2=0.011, cost_usd=0.0011, wh=0.03),
                      tier="moderate", correct=True, escalated_from="trivial")
    e = store.get_run_events(r)[0]
    for key in ("seq", "task_id", "arm", "role", "tier", "gco2", "cost_usd", "wh",
                "correct", "escalated_from", "energy_label", "intensity_label"):
        assert key in e, f"frozen event key {key!r} missing"
    assert e["correct"] is True
    assert e["escalated_from"] == "trivial"
    assert e["intensity_label"] == "live"


def test_completed_tuples_tracks_answer_units_for_resume(db):
    """A (task, arm, k) unit is 'done' once its answer row lands — overhead rows
    (classifier/judge) alone don't count. This is the resume key that prevents
    duplicate (task, arm, k) rows after a mid-run kill."""
    r = store.create_run("run-1")
    # unit fully processed: classifier + answer
    store.record_call(r, "t1", "b", 0, "classifier", _impact())
    store.record_call(r, "t1", "b", 0, "answer", _impact())
    # unit only started (classifier, no answer yet) — must NOT be considered done
    store.record_call(r, "t2", "b", 0, "classifier", _impact())
    done = store.completed_tuples(r)
    assert ("t1", "b", 0) in done
    assert ("t2", "b", 0) not in done


def test_run_totals_sum_per_arm_with_escalations(db):
    """Totals are per-arm and count every call including overhead (D4); escalation
    count reflects answer rows that escalated. These feed the race counters/report."""
    r = store.create_run("run-1")
    store.record_call(r, "t1", "a", 0, "answer", _impact(gco2=1.0, cost_usd=0.10))
    store.record_call(r, "t1", "b", 0, "classifier", _impact(gco2=0.1, cost_usd=0.01))
    store.record_call(r, "t1", "b", 0, "answer", _impact(gco2=0.2, cost_usd=0.02),
                      escalated_from="trivial")
    tot = store.run_totals(r)
    assert tot["a"]["gco2"] == pytest.approx(1.0)
    assert tot["a"]["calls"] == 1
    assert tot["a"]["escalations"] == 0
    assert tot["b"]["gco2"] == pytest.approx(0.3)  # 0.1 + 0.2, overhead included
    assert tot["b"]["calls"] == 2
    assert tot["b"]["escalations"] == 1


def test_list_runs_newest_first(db):
    """Pickers (`ember race`/`report` with no run_id) take the latest run first."""
    store.create_run("run-old")
    store.create_run("run-new")
    ids = [r["id"] for r in store.list_runs()]
    assert ids[0] == "run-new"
    assert set(ids) == {"run-old", "run-new"}


def test_report_roundtrip_and_replace(db):
    """save_report/load_report round-trips the dict; a second save replaces, not
    duplicates (Report is keyed by run_id)."""
    r = store.create_run("run-1")
    assert store.load_report(r) is None
    store.save_report(r, {"headline": {"co2_reduction_pct": 60}})
    assert store.load_report(r)["headline"]["co2_reduction_pct"] == 60
    store.save_report(r, {"headline": {"co2_reduction_pct": 42}})
    assert store.load_report(r)["headline"]["co2_reduction_pct"] == 42


def test_survives_process_restart(db):
    """A fresh engine bound to the same file still serves runs, events, and reports —
    this is offline replay after a restart (KR4.1). Simulated by rebinding engine."""
    r = store.create_run("run-1")
    store.record_call(r, "t1", "a", 0, "answer", _impact())
    store.save_report(r, {"ok": True})
    db["rebind"]()  # new engine, same file — as if the process restarted
    assert [x["id"] for x in store.list_runs()] == ["run-1"]
    assert len(store.get_run_events("run-1")) == 1
    assert store.load_report("run-1") == {"ok": True}


def test_concurrent_writers_get_unique_contiguous_seqs(db):
    """~4 harness threads write at once (spec 06 concurrency note); the seq lock +
    WAL must yield unique, gap-free seqs — no two calls share a cursor value."""
    r = store.create_run("run-1")
    seqs: list[int] = []
    lock = threading.Lock()

    def worker(n):
        for _ in range(n):
            s = store.record_call(r, "t", "b", 0, "answer", _impact())
            with lock:
                seqs.append(s)

    threads = [threading.Thread(target=worker, args=(25,)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(seqs) == list(range(1, 101))  # 4×25, unique + contiguous
