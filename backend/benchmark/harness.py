"""A/B harness (spec 05 / D14, task P3-M2 — KR1.2).

Arm A (baseline): every task → MODEL_HARD (latest Opus) at BASELINE_ZONE.
Arm B (Ember):    route() — right-size + gate + simulated greenest zone.

Interleaved A,B per (task, k) inside one worker — no arm-level batching, so
partial runs are still balanced pairs. Bounded concurrency with exponential
backoff on 429. Every call committed to SQLite immediately (resumable). Failed
attempts stay in the totals as error rows (spec 05 honesty guardrails; note:
a transport-level failure has no usage field, so its cost/energy is recorded
as zero — we cannot know what the provider metered, and we never guess).

Contract note for P2 (also in spec 05): each entry of route()'s calls[] must
carry "role" (answer|classifier|judge) and "tier" alongside the measure()
record — D4 auditability. The harness defensively defaults a missing role to
"answer" on the final call and "judge" otherwise, and logs that it did.

CLI: uv run ember benchmark [--limit N] [--k K] [--resume RUN_ID] [--yes]
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from backend import config
from backend.benchmark import scoring, workloads
from backend.db import store
from backend.measurement import calculator
from backend.providers import registry
from backend.providers.base import ProviderError

BACKOFF_TRIES = 5
# Rough per-call token guess for the up-front spend estimate ONLY (the real run
# uses exact usage counts). Deliberately conservative (high).
EST_TOKENS_IN, EST_TOKENS_OUT = 200, 400


def _with_backoff(fn):
    for attempt in range(BACKOFF_TRIES):
        try:
            return fn()
        except ProviderError as e:
            if "429" in str(e) and attempt < BACKOFF_TRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def spend_estimate_usd(n_tasks: int, k: int) -> float:
    """Upper bound: arm A all-Opus + arm B assumed all-moderate + judge each."""
    a = calculator.cost_usd(config.MODEL_LADDER["hard"], EST_TOKENS_IN, EST_TOKENS_OUT)
    b = calculator.cost_usd(config.MODEL_LADDER["moderate"], EST_TOKENS_IN, EST_TOKENS_OUT)
    j = calculator.cost_usd(config.JUDGE_MODEL, EST_TOKENS_IN + EST_TOKENS_OUT, 20)
    return n_tasks * k * (a + b + j)


def _run_arm_a(run_id: str, task: dict, k_index: int) -> None:
    try:
        result = _with_backoff(lambda: registry.chat(
            config.MODEL_LADDER["hard"], [{"role": "user", "content": task["prompt"]}]))
        impact = calculator.measure(result.model_key, result.tokens_in,
                                    result.tokens_out, config.BASELINE_ZONE)
        s = scoring.score(task, result.text)
        store.record_call(run_id, task["id"], "a", k_index, "answer", impact,
                          tier="hard", answer=result.text, latency_ms=result.latency_ms,
                          score=s["score"], correct=s["correct"])
    except Exception as e:  # failed attempts stay in totals (as error rows)
        store.record_call(run_id, task["id"], "a", k_index, "answer", None,
                          model_key=config.MODEL_LADDER["hard"], tier="hard",
                          correct=False, error=str(e)[:500])


def _run_arm_b(run_id: str, task: dict, k_index: int) -> None:
    from backend.router.route import route  # P2's module — imported lazily

    try:
        result = _with_backoff(lambda: route(task["prompt"]))
        calls = result["calls"]
        s = scoring.score(task, result["answer"])
        for i, call in enumerate(calls):
            last = i == len(calls) - 1
            role = call.get("role") or ("answer" if last else "judge")
            store.record_call(
                run_id, task["id"], "b", k_index, role, call,
                tier=call.get("tier") or (result["tier_final"] if last else None),
                latency_ms=call.get("latency_ms", 0.0),
                answer=result["answer"] if last else None,
                score=s["score"] if last else call.get("score"),
                correct=s["correct"] if last else None,
                escalated_from=(result["tier_first"] if last and result["tier_final"] != result["tier_first"] else None),
            )
    except Exception as e:
        store.record_call(run_id, task["id"], "b", k_index, "answer", None,
                          model_key="", correct=False, error=str(e)[:500])


def run(workload: str = "default", k: int = 3, limit: int | None = None,
        assume_yes: bool = False, resume: str | None = None) -> str:
    tasks = workloads.load(workload, limit=limit)
    store.init_db()

    if resume:
        run_id, done = resume, store.completed_tuples(resume)
        print(f"resuming {run_id}: {len(done)} of {len(tasks) * k * 2} arm-calls already complete")
    else:
        run_id = store.create_run(k=k, workload=workload)
        done = set()

    est = spend_estimate_usd(len(tasks), k)
    print(f"run {run_id}: {len(tasks)} tasks × {k} repeats × 2 arms — "
          f"estimated spend ceiling ${est:.2f} (real run uses exact usage)")
    if not assume_yes and sys.stdin.isatty():
        if input("proceed? [y/N] ").strip().lower() != "y":
            print("aborted before any paid call")
            return run_id

    def work(item):
        task, k_index = item
        # A then B back-to-back per (task, k): interleaved pairs, never arm batches
        if (task["id"], "a", k_index) not in done:
            _run_arm_a(run_id, task, k_index)
        if (task["id"], "b", k_index) not in done:
            _run_arm_b(run_id, task, k_index)

    items = [(task, k_i) for k_i in range(k) for task in tasks]
    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENCY) as pool:
        list(pool.map(work, items))

    store.finish_run(run_id)

    from backend.benchmark import report
    rpt = report.build(run_id)
    h = rpt["headline"]
    delta = rpt.get("evaluation", {}).get("layer1", {}).get("delta_pp")
    print(f"\nEmber cut CO2 by {h['co2_reduction_pct']:.1f}% (est) at "
          f"{delta if delta is not None else '?'}pp accuracy delta vs all-Opus, "
          f"{h['cost_reduction_pct']:.1f}% cost saving (exact).")
    return run_id


if __name__ == "__main__":
    raise SystemExit(run())
