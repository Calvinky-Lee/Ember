"""Store API (spec 06) — SQLite is the single source of truth; the event stream
read from it is what `ember race` animates and the harness resumes from.

Design rules honored here (spec 06):
- One row per call (answer, classifier, judge) so D4 overhead accounting is
  auditable straight from SQL.
- `seq` is a monotonically increasing per-run cursor: the TUI's incremental read
  key and the guarantee that replays reproduce the original order.
- Writers commit per call, never batch — a crash loses at most one call.

Concurrency: the harness writes from ~4 worker threads. SQLite runs in serialized
mode with per-call commits; WAL + a busy timeout keep concurrent writers from
tripping over each other, and a process-local lock makes per-run `seq` allocation
atomic (max(seq)+1 read-then-insert must not interleave)."""
import json
import threading
from datetime import datetime, timezone

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from backend import config
from backend.db.models import Base, CarbonSnapshot, QueryResult, Report, Run

DB_PATH = config.DATA / "ember.sqlite"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    # Harness workers touch the store from multiple threads; SQLAlchemy's default
    # sqlite pool hands each thread its own connection, so allow cross-thread use.
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """WAL lets a reader (ember race) run while writers (harness) commit; the busy
    timeout makes a briefly-locked write wait instead of raising."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


# Serializes the read-max-seq / insert pair so two threads never claim the same
# per-run seq. Cheap: the critical section is one tiny transaction.
_seq_lock = threading.Lock()


def init_db() -> None:
    config.DATA.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Run lifecycle -----------------------------------------------------------

def create_run(run_id: str | None = None, *, k: int = 3, workload: str = "default",
               config_snapshot: dict | None = None) -> str:
    """Open a run row (status 'running'). config_snapshot pins the ladder/floor/zones
    so any report is reproducible/explainable later (spec 06). Returns the run_id."""
    run_id = run_id or _now().strftime("run-%Y%m%d-%H%M%S-") + f"{id(object()) & 0xffff:04x}"
    snap = config_snapshot if config_snapshot is not None else default_config_snapshot()
    with Session(engine) as s:
        s.add(Run(id=run_id, started_at=_now(), finished_at=None, status="running",
                  k=k, workload=workload, config_json=json.dumps(snap)))
        s.commit()
    return run_id


def finish_run(run_id: str, status: str = "done") -> None:
    """Close a run: stamp finished_at + terminal status (done|failed)."""
    with Session(engine) as s:
        run = s.get(Run, run_id)
        if run is None:
            raise KeyError(f"No run {run_id!r}")
        run.status = status
        run.finished_at = _now()
        s.commit()


def default_config_snapshot() -> dict:
    """The reproducibility snapshot: everything a report needs to be explained later."""
    return {
        "model_ladder": config.MODEL_LADDER,
        "judge_model": config.JUDGE_MODEL,
        "baseline_zone": config.BASELINE_ZONE,
        "carbon_zones": config.CARBON_ZONES,
        "quality_floor": config.QUALITY_FLOOR,
        "confidence_floor": config.CONFIDENCE_FLOOR,
        "pue": config.PUE,
    }


# --- The write path: one row per call ---------------------------------------

def record_call(run_id: str, task_id: str, arm: str, k_index: int, role: str,
                impact: dict | None = None, *, model_key: str | None = None,
                tier: str | None = None, latency_ms: float = 0.0,
                score: float | None = None, correct: bool | None = None,
                answer: str | None = None,
                escalated_from: str | None = None, error: str | None = None) -> int:
    """Persist one call (answer|classifier|judge) and return its per-run `seq`.

    `impact` is a `calculator.measure(...)` record — it carries tokens, wh, gco2,
    cost, zone, and the provenance labels. Overhead/error rows may pass a partial
    dict or None. Commits immediately (resume support); never batched."""
    impact = impact or {}
    correct_int = None if correct is None else int(bool(correct))
    with _seq_lock:
        with Session(engine) as s:
            last = s.execute(
                select(func.max(QueryResult.seq)).where(QueryResult.run_id == run_id)
            ).scalar()
            seq = (last or 0) + 1
            s.add(QueryResult(
                run_id=run_id, task_id=task_id, arm=arm, k_index=k_index, seq=seq,
                role=role,
                model_key=model_key or impact.get("model_key") or "",
                tier=tier,
                tokens_in=int(impact.get("tokens_in", 0) or 0),
                tokens_out=int(impact.get("tokens_out", 0) or 0),
                wh=float(impact.get("wh", 0.0) or 0.0),
                gco2=float(impact.get("gco2", 0.0) or 0.0),
                cost_usd=float(impact.get("cost_usd", 0.0) or 0.0),
                latency_ms=float(latency_ms or 0.0),
                zone=impact.get("zone"),
                gco2_per_kwh=impact.get("gco2_per_kwh"),
                intensity_label=impact.get("intensity_label"),
                energy_label=impact.get("energy_label", "estimated"),
                score=score,
                correct=correct_int,
                answer=answer,
                escalated_from=escalated_from,
                error=error,
            ))
            s.commit()
            return seq


# --- The read path: the race-view feed --------------------------------------

def _event_dict(r: QueryResult) -> dict:
    """The frozen event shape `ember race` renders (spec 06). Fields at the top of
    the dict are the frozen contract; the rest are additive extras for the ticker."""
    return {
        "seq": r.seq,
        "task_id": r.task_id,
        "arm": r.arm,
        "role": r.role,
        "tier": r.tier,
        "gco2": r.gco2,
        "cost_usd": r.cost_usd,
        "wh": r.wh,
        "correct": None if r.correct is None else bool(r.correct),
        "escalated_from": r.escalated_from,
        "energy_label": r.energy_label,
        "intensity_label": r.intensity_label,
        # additive extras (safe to ignore) — used by the ticker / debugging
        "k_index": r.k_index,
        "model_key": r.model_key,
        "tokens_in": r.tokens_in,
        "tokens_out": r.tokens_out,
        "latency_ms": r.latency_ms,
        "zone": r.zone,
        "gco2_per_kwh": r.gco2_per_kwh,
        "score": r.score,
        "error": r.error,
    }


def get_run_events(run_id: str, after_seq: int = 0) -> list[dict]:
    """Events with seq > after_seq, ordered — exactly the tail since the last poll.
    This is the `ember race` incremental feed and a replay source."""
    with Session(engine) as s:
        rows = s.execute(
            select(QueryResult)
            .where(QueryResult.run_id == run_id, QueryResult.seq > after_seq)
            .order_by(QueryResult.seq)
        ).scalars().all()
        return [_event_dict(r) for r in rows]


def run_totals(run_id: str) -> dict:
    """Per-arm sums (gco2, cost, wh, tokens, calls) + escalation count — the numbers
    the race counters and the report per-arm block are built from. Every call is
    counted, overhead included (D4)."""
    out: dict = {}
    with Session(engine) as s:
        rows = s.execute(
            select(
                QueryResult.arm,
                func.sum(QueryResult.gco2),
                func.sum(QueryResult.cost_usd),
                func.sum(QueryResult.wh),
                func.sum(QueryResult.tokens_in),
                func.sum(QueryResult.tokens_out),
                func.count(QueryResult.id),
                func.sum(QueryResult.latency_ms),
            ).where(QueryResult.run_id == run_id).group_by(QueryResult.arm)
        ).all()
        for arm, gco2, cost, wh, tin, tout, calls, latency in rows:
            out[arm] = {
                "gco2": gco2 or 0.0,
                "cost_usd": cost or 0.0,
                "wh": wh or 0.0,
                "tokens_in": int(tin or 0),
                "tokens_out": int(tout or 0),
                "calls": int(calls or 0),
                "latency_ms": latency or 0.0,
            }
        # escalation count per arm: answer rows that escalated from a lower tier
        esc = s.execute(
            select(QueryResult.arm, func.count(QueryResult.id)).where(
                QueryResult.run_id == run_id,
                QueryResult.escalated_from.is_not(None),
            ).group_by(QueryResult.arm)
        ).all()
        for arm, count in esc:
            out.setdefault(arm, {})["escalations"] = int(count or 0)
        for arm in out:
            out[arm].setdefault("escalations", 0)
    return out


def completed_tuples(run_id: str) -> set[tuple[str, str, int]]:
    """(task_id, arm, k_index) units that already produced an accepted answer row.
    The harness skips these on resume → zero duplicate (task, arm, k) rows."""
    with Session(engine) as s:
        rows = s.execute(
            select(QueryResult.task_id, QueryResult.arm, QueryResult.k_index)
            .where(QueryResult.run_id == run_id, QueryResult.role == "answer",
                   QueryResult.error.is_(None))  # error rows re-run on resume ("accepted")
            .distinct()
        ).all()
        return {(t, a, k) for t, a, k in rows}


def list_runs() -> list[dict]:
    """Runs newest-first — for the `ember race` / `ember report` pickers."""
    with Session(engine) as s:
        rows = s.execute(select(Run).order_by(Run.started_at.desc())).scalars().all()
        return [{
            "id": r.id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "k": r.k,
            "workload": r.workload,
        } for r in rows]


# --- Reports -----------------------------------------------------------------

def save_report(run_id: str, report: dict) -> None:
    """Persist (or replace) a run's report JSON — served offline by `ember report`."""
    with Session(engine) as s:
        existing = s.get(Report, run_id)
        payload = json.dumps(report)
        if existing is None:
            s.add(Report(run_id=run_id, report_json=payload, created_at=_now()))
        else:
            existing.report_json = payload
            existing.created_at = _now()
        s.commit()


def load_report(run_id: str) -> dict | None:
    """The stored report dict, or None if this run has none yet."""
    with Session(engine) as s:
        rep = s.get(Report, run_id)
        return json.loads(rep.report_json) if rep else None


# --- Carbon snapshots (audit trail for the intensity used) -------------------

def save_snapshot(zone: str, gco2_per_kwh: float, label: str, fetched_at: str) -> None:
    """Append an intensity observation — an auditable record of what the grid was
    when a call was measured (distinct from the last-good file carbon.py keeps)."""
    with Session(engine) as s:
        s.add(CarbonSnapshot(zone=zone, gco2_per_kwh=gco2_per_kwh,
                             label=label, fetched_at=fetched_at))
        s.commit()


# --- Evaluation & report reads (spec 09 raw material) -------------------------

def get_answer_rows(run_id: str) -> list[dict]:
    """Answer-role rows with text + scores — the evaluation module's raw material
    (spec 09: 'computes all three layers from a finished run's SQLite rows')."""
    with Session(engine) as s:
        rows = s.execute(
            select(QueryResult)
            .where(QueryResult.run_id == run_id, QueryResult.role == "answer")
            .order_by(QueryResult.seq)
        ).scalars().all()
        return [{
            "task_id": r.task_id, "arm": r.arm, "k_index": r.k_index,
            "tier": r.tier, "answer": r.answer, "score": r.score,
            "correct": None if r.correct is None else bool(r.correct),
            "error": r.error, "latency_ms": r.latency_ms,
        } for r in rows]


def get_query_latencies(run_id: str) -> dict:
    """arm → list of per-(task, k) total latencies. Arm B totals include overhead
    roles (classifier/judge) — comparing only its answer calls against arm A's
    would flatter Ember; the honest p50 is wall-clock per query."""
    from collections import defaultdict
    per_query: dict = defaultdict(float)
    with Session(engine) as s:
        rows = s.execute(select(QueryResult)
                         .where(QueryResult.run_id == run_id)).scalars().all()
        for r in rows:
            per_query[(r.arm, r.task_id, r.k_index)] += r.latency_ms or 0.0
    out: dict = {"a": [], "b": []}
    for (arm, _t, _k), total in per_query.items():
        out.setdefault(arm, []).append(total)
    return out


def get_run_config(run_id: str) -> dict:
    """The reproducibility snapshot stored at create_run time."""
    with Session(engine) as s:
        run = s.get(Run, run_id)
        return json.loads(run.config_json) if run else {}
