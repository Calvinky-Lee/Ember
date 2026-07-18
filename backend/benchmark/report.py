"""Report builder (specs 05 + 09, tasks P3-M3/M4 — KR1.3, KR2.x, KR3.4).

Assembles the full report dict from a run's SQLite rows and persists it.
P4's `ember report` renders this; the harness prints its headline line.
"""
import statistics

from backend import config
from backend.benchmark import evaluation, workloads
from backend.db import store

FLEET_QUERIES_PER_DAY = 1_000_000


def _pct_reduction(a: float, b: float) -> float:
    return round(100 * (a - b) / a, 1) if a else 0.0


def build(run_id: str, chat_fn=None, with_judge_layers: bool = True) -> dict:
    runs = {r["id"]: r for r in store.list_runs()}
    meta = runs.get(run_id)
    if meta is None:
        raise KeyError(f"unknown run {run_id!r}")

    tasks = workloads.load(meta["workload"])
    rows = store.get_answer_rows(run_id)
    totals = store.run_totals(run_id)
    latencies = store.get_query_latencies(run_id)
    a, b = totals["a"], totals["b"]

    eval_block = evaluation.evaluate(rows, tasks, k=meta["k"], chat_fn=chat_fn,
                                     with_judge_layers=with_judge_layers)

    # answers/errors counted from the raw rows (run_totals sums impact only)
    n_answers = {arm: sum(1 for r in rows if r["arm"] == arm) for arm in ("a", "b")}
    n_errors = {arm: sum(1 for r in rows if r["arm"] == arm and r["error"]) for arm in ("a", "b")}

    p50 = {arm: round(statistics.median(vals), 0) if vals else None
           for arm, vals in latencies.items()}
    per_query_gco2 = {arm: (t["gco2"] / n_answers[arm] if n_answers[arm] else 0.0)
                      for arm, t in totals.items()}
    saved_g = per_query_gco2["a"] - per_query_gco2["b"]

    # Intensity provenance: the run is only as live as its weakest attribution.
    labels = {r["intensity_label"] for r in store.get_run_events(run_id) if r["intensity_label"]}
    intensity_mode = ("live" if labels <= {"live", "cached"} else
                      "fallback" if labels == {"fallback"} else "mixed")

    report = {
        "run_id": run_id,
        "headline": {
            "co2_reduction_pct": _pct_reduction(a["gco2"], b["gco2"]),
            "accuracy_delta_pp": eval_block["layer1"].get("delta_pp"),
            "cost_reduction_pct": _pct_reduction(a["cost_usd"], b["cost_usd"]),
            "latency_p50_ms": p50,
        },
        "per_arm": {
            arm: {"gco2": round(t["gco2"], 4), "cost_usd": round(t["cost_usd"], 4),
                  "wh": round(t["wh"], 2), "calls": t["calls"],
                  "answers": n_answers[arm], "errors": n_errors[arm]}
            for arm, t in totals.items()
        },
        "escalation": {
            "count": b["escalations"],
            "rate": round(b["escalations"] / n_answers["b"], 3) if n_answers["b"] else 0.0,
        },
        "sci": {
            "per_query_gco2": {arm: round(v, 5) for arm, v in per_query_gco2.items()},
            "functional_unit": "one query",
            "m": 0,
            "note": "SCI = (E×I + M)/R; M=0 declared (embodied out of scope)",
        },
        "extrapolation": {
            "queries_per_day": FLEET_QUERIES_PER_DAY,
            # saved gCO2/query × 1e6 queries/day × 365 days ÷ 1e6 g/tonne = saved×365
            "tonnes_co2_per_year_saved": round(saved_g * 365, 1),
            "label": "estimated",
        },
        "evaluation": eval_block,
        "labels": {"energy": "estimated", "cost": "exact", "intensity_mode": intensity_mode},
        "config": store.get_run_config(run_id),
    }
    store.save_report(run_id, report)
    return report
