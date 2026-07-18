"""Up-front spend estimator for the harness (task P1-M4, spec 05).

The harness prints a spend estimate and asks for confirmation *before* the first
Opus call, so credit exhaustion is never a surprise (spec 05 edge case). Cost here
is EXACT price-sheet math per token (D7) — the only estimate is the assumed average
token counts per call, which the caller supplies.

Arm A (baseline) is every task → MODEL_HARD, so its cost is a tight estimate.
Arm B (Ember) routes, so its *actual* cost is lower and unknown up front; we report
a conservative worst-case (all-hard, judge included) as the ceiling the confirm
prompt should quote."""
from backend import config
from backend.measurement.calculator import cost_usd


def _per_call(model_key: str, tin: int, tout: int) -> float:
    return cost_usd(model_key, tin, tout)


def estimate_spend(n_tasks: int, k: int = 3, *, avg_tokens_in: int = 400,
                   avg_tokens_out: int = 300) -> dict:
    """Estimate the total USD a run will spend before it starts.

    n_tasks × k = calls per arm. Arm A: one MODEL_HARD call each. Arm B ceiling:
    one MODEL_HARD answer + one judge call each (worst case — every query escalates
    to the top and gets judged). Real Arm B lands well under this because most
    queries resolve on the small/mid tiers."""
    calls = n_tasks * k
    hard = config.MODEL_LADDER["hard"]
    judge = config.JUDGE_MODEL

    a_per = _per_call(hard, avg_tokens_in, avg_tokens_out)
    arm_a = a_per * calls

    # Arm B worst case: top-tier answer + a judge pass on every call.
    b_answer = _per_call(hard, avg_tokens_in, avg_tokens_out)
    b_judge = _per_call(judge, avg_tokens_in + avg_tokens_out, 50)
    arm_b_ceiling = (b_answer + b_judge) * calls

    return {
        "n_tasks": n_tasks,
        "k": k,
        "calls_per_arm": calls,
        "assumptions": {"avg_tokens_in": avg_tokens_in, "avg_tokens_out": avg_tokens_out,
                        "note": "cost is exact per token; token averages are the estimate"},
        "arm_a_usd": arm_a,
        "arm_b_ceiling_usd": arm_b_ceiling,
        "total_ceiling_usd": arm_a + arm_b_ceiling,
        "models": {"hard": hard, "judge": judge},
        "label": "estimate (exact price sheet × assumed token averages)",
    }


def format_estimate(est: dict) -> str:
    """One human-readable block for the harness confirm prompt."""
    return (
        f"Spend estimate — {est['n_tasks']} tasks × K={est['k']} = "
        f"{est['calls_per_arm']} calls/arm\n"
        f"  Arm A (all {est['models']['hard']}):   ~${est['arm_a_usd']:.2f}\n"
        f"  Arm B (Ember, worst case):  ~${est['arm_b_ceiling_usd']:.2f} "
        f"(judge {est['models']['judge']} included; real cost lower)\n"
        f"  Total ceiling:              ~${est['total_ceiling_usd']:.2f}\n"
        f"  [{est['label']}]"
    )


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    print(format_estimate(estimate_spend(n, k)))
