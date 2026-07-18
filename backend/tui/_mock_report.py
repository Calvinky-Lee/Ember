"""Dev-only fixture (P4-M3): a report dict matching backend.benchmark.report.build()'s
REAL output shape (verified against the landed implementation, not just the spec
prose) so backend.report_html.render() can be tested without running a real
benchmark. Never imported by shipped code."""

REPORT: dict = {
    "run_id": "dev-mock-0001",
    "headline": {
        "co2_reduction_pct": 71.4,
        "accuracy_delta_pp": -0.8,
        "cost_reduction_pct": 82.6,
        "latency_p50_ms": {"a": 2140.0, "b": 640.0},
    },
    "per_arm": {
        "a": {"gco2": 2.014, "cost_usd": 0.2303, "wh": 210.4, "calls": 150,
              "answers": 150, "errors": 0},
        "b": {"gco2": 0.576, "cost_usd": 0.0401, "wh": 61.2, "calls": 192,
              "answers": 150, "errors": 1},
    },
    "escalation": {"count": 21, "rate": 0.14},
    "sci": {
        "per_query_gco2": {"a": 0.01343, "b": 0.00384},
        "functional_unit": "one query",
        "m": 0,
        "note": "SCI = (E×I + M)/R; M=0 declared (embodied out of scope)",
    },
    "extrapolation": {
        "queries_per_day": 1_000_000,
        "tonnes_co2_per_year_saved": 524.8,
        "label": "estimated",
    },
    "labels": {"energy": "estimated", "cost": "exact", "intensity_mode": "fallback"},
    "evaluation": {
        "layer1": {"acc_a": 0.98, "acc_b": 0.967, "delta_pp": -1.3,
                   "ci95_pp": [-2.6, 0.1], "n_tasks": 100, "seed": 42, "k": 3},
        "layer2": {"wins_b": 18, "ties": 24, "losses_b": 8, "position_flips": 3,
                   "n_judged": 50, "inconclusive": False},
        "layer3": {"judge_agreement_pct": 91.0, "judge_false_pass_pct": 3.5, "n_checked": 40},
        "per_tier": [
            {"tier": "trivial", "n": 89, "delta_pp": -0.4},
            {"tier": "moderate", "n": 41, "delta_pp": -1.1},
            {"tier": "hard", "n": 20, "delta_pp": 0.0},
        ],
        "parity_criterion": "CI within ±2pp",
        "parity_met": True,
    },
    "config": {
        "model_ladder": {"trivial": "groq:llama-3.1-8b-instant",
                          "moderate": "groq:llama-3.3-70b-versatile",
                          "hard": "anthropic:claude-opus-4-8"},
        "judge_model": "gemini:gemini-2.5-flash",
        "baseline_zone": "US-MIDA-PJM",
        "quality_floor": 0.85, "confidence_floor": 0.80, "pue": 1.2,
    },
}

# A skipped-layers variant — evaluation.py degrades gracefully when there are no
# paired ground-truth tasks or the judge is unreachable; the renderer must not crash.
REPORT_DEGRADED: dict = {
    **REPORT,
    "evaluation": {
        "layer1": {"skipped": "no paired ground-truth tasks"},
        "layer2": {"skipped": "judge unavailable: GEMINI_API_KEY not set"},
        "layer3": {"skipped": "judge unavailable: GEMINI_API_KEY not set"},
        "per_tier": [],
        "parity_criterion": "CI within ±2pp",
        "parity_met": False,
    },
}
