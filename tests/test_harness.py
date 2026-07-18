"""A/B harness (spec 05, D14) — interleaving, resume, backoff, and the honesty
guardrail that failures stay in the totals. Runs fully offline: providers and the
router are faked; persistence is real (tmp SQLite) because resume semantics ARE
the thing under test."""
import json

import pytest

from backend import config
from backend.benchmark import harness
from backend.providers.base import ChatResult, ProviderError


def _fake_chat_result(text="Paris", model_key=None):
    return ChatResult(text=text, tokens_in=10, tokens_out=5, latency_ms=50.0,
                      model_key=model_key or config.MODEL_LADDER["hard"])


def _fake_route_result(answer="Paris", tier="trivial"):
    call = {"model_key": config.MODEL_LADDER["trivial"], "tokens_in": 10,
            "tokens_out": 5, "wh": 0.001, "gco2": 0.0001, "cost_usd": 0.00001,
            "zone": "SE", "gco2_per_kwh": 25.0, "intensity_label": "fallback",
            "energy_label": "estimated", "role": "answer", "tier": tier,
            "latency_ms": 30.0}
    return {"answer": answer, "tier_first": tier, "tier_final": tier,
            "escalations": [], "calls": [call],
            "totals": {"gco2": 0.0001, "cost_usd": 0.00001, "wh": 0.001,
                       "latency_ms": 30.0}}


@pytest.fixture
def bench_env(tmp_store, monkeypatch, tmp_path):
    """Offline benchmark environment: 3-task workload (one per deterministic
    oracle type), fake providers/router, serial execution for deterministic
    ordering assertions."""
    wl_dir = tmp_path / "workloads"
    wl_dir.mkdir(exist_ok=True)
    tasks = [
        {"id": "t-num", "category": "trivial", "prompt": "What is 2+2? Reply with only the number.",
         "oracle": {"type": "numeric_exact", "answer": "4"}},
        {"id": "t-str", "category": "trivial", "prompt": "Capital of France? One word.",
         "oracle": {"type": "string_match", "answer": "Paris"}},
        {"id": "t-judge", "category": "reasoning", "prompt": "why?",
         "oracle": {"type": "judge", "reference": "because"}},
    ]
    (wl_dir / "mini.json").write_text(json.dumps({"tasks": tasks}))
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "MAX_CONCURRENCY", 1)

    calls = {"a": 0, "b": 0}

    def fake_chat(model_key, messages, **kw):
        calls["a"] += 1
        return _fake_chat_result(text="The answer is 4. Paris.")

    def fake_route(query):
        calls["b"] += 1
        return _fake_route_result(answer="4 — Paris")

    monkeypatch.setattr("backend.providers.registry.chat", fake_chat)
    monkeypatch.setattr("backend.router.route.route", fake_route)
    # The end-of-run report build invokes the judge (evaluation layers 2/3) via
    # registry.chat — stub it here so call counters only see harness traffic;
    # judge-layer behavior has its own tests in test_evaluation.py.
    monkeypatch.setattr("backend.benchmark.evaluation._judge_chat", lambda messages: "yes")
    return tmp_store, calls


def test_run_interleaves_arms_per_task(bench_env):
    """D14: A,B,A,B per task — never arm-level batching, so a killed run still
    holds balanced pairs. With concurrency 1 the seq order must strictly
    alternate a,b within each task."""
    store, _ = bench_env
    run_id = harness.run(workload="mini", k=1, assume_yes=True)
    events = [e for e in store.get_run_events(run_id) if e["role"] == "answer"]
    arms = [(e["task_id"], e["arm"]) for e in events]
    assert arms == [("t-num", "a"), ("t-num", "b"), ("t-str", "a"), ("t-str", "b"),
                    ("t-judge", "a"), ("t-judge", "b")]


def test_scoring_happens_inline_and_judge_tasks_stay_unscored(bench_env):
    """Ground-truth oracles are scored at harness time (Layer 1's raw material);
    judge-oracle tasks must remain correct=None for evaluation-time blind judging
    — a harness that pre-judged them would leak verdicts into the blind design."""
    store, _ = bench_env
    run_id = harness.run(workload="mini", k=1, assume_yes=True)
    rows = {(r["task_id"], r["arm"]): r for r in store.get_answer_rows(run_id)}
    assert rows[("t-num", "a")]["correct"] is True
    assert rows[("t-str", "b")]["correct"] is True
    assert rows[("t-judge", "a")]["correct"] is None


def test_resume_skips_completed_and_reruns_failures(bench_env, monkeypatch):
    """Kill-and-resume is the crash insurance for the paid overnight-equivalent
    run (spec 05 acceptance): a resumed run must re-execute ONLY the tuples that
    failed or never ran — zero duplicate rows, zero re-paid completed calls."""
    store, calls = bench_env

    import backend.router.route as route_mod
    good_route = route_mod.route  # the fixture's fake — restored after the crash phase

    def failing_route(query):
        raise RuntimeError("simulated crash on arm B")

    monkeypatch.setattr(route_mod, "route", failing_route)
    run_id = harness.run(workload="mini", k=1, assume_yes=True)
    b_errors = [r for r in store.get_answer_rows(run_id) if r["arm"] == "b" and r["error"]]
    assert len(b_errors) == 3  # all B calls failed

    monkeypatch.setattr(route_mod, "route", good_route)
    calls["a"] = calls["b"] = 0
    harness.run(workload="mini", k=1, assume_yes=True, resume=run_id)
    # arm A was complete → zero new A calls; all 3 B tuples re-ran
    assert calls == {"a": 0, "b": 3}
    answers = [r for r in store.get_answer_rows(run_id) if r["arm"] == "b" and not r["error"]]
    assert len(answers) == 3


def test_429_backoff_retries_then_succeeds(bench_env, monkeypatch):
    """Opus rate limits are a certainty during the real run (spec 05 edge case).
    A 429 must be retried with backoff and eventually succeed — not fail the task
    and not retry non-429 errors (those record as failures immediately)."""
    store, _ = bench_env
    monkeypatch.setattr(harness.time, "sleep", lambda s: None)  # no real waiting
    attempts = {"n": 0}

    def flaky_chat(model_key, messages, **kw):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise ProviderError("anthropic HTTP 429: rate limited")
        return _fake_chat_result()

    monkeypatch.setattr("backend.providers.registry.chat", flaky_chat)
    run_id = harness.run(workload="mini", k=1, limit=1, assume_yes=True)
    assert attempts["n"] == 3  # two 429s + one success
    assert not any(r["error"] for r in store.get_answer_rows(run_id) if r["arm"] == "a")


def test_failures_stay_in_totals_and_report_still_builds(bench_env, monkeypatch):
    """Honesty guardrail (spec 05): 'never exclude failed queries.' A dead arm B
    must produce error rows counted as incorrect, and the report must still build
    offline — with parity_met False, not a crash and not silent omission."""
    store, _ = bench_env
    import backend.router.route as route_mod
    monkeypatch.setattr(route_mod, "route",
                        lambda q: (_ for _ in ()).throw(RuntimeError("router down")))
    run_id = harness.run(workload="mini", k=1, assume_yes=True)

    from backend.benchmark import report
    rpt = report.build(run_id, with_judge_layers=False)
    assert rpt["per_arm"]["b"]["errors"] == 3
    assert rpt["evaluation"]["parity_met"] is False
    assert store.load_report(run_id) is not None  # persisted for offline demo


def test_spend_estimate_is_priced_from_the_real_table():
    """The up-front spend confirm (spec 05) must scale with tasks×k and use the
    actual price table — a hardcoded guess would let credit exhaustion kill the
    real run halfway (the exact failure the estimate exists to prevent)."""
    one = harness.spend_estimate_usd(1, 1)
    assert one > 0
    assert harness.spend_estimate_usd(150, 3) == pytest.approx(one * 450)
