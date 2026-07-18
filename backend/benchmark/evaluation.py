"""Evaluation statistics (spec 09, task P3-M4 — KR1.3, KR3.4).

Three layers, strongest evidence first:
  Layer 1 — paired accuracy on ground-truth tasks + paired-bootstrap 95% CI.
  Layer 2 — blind, position-swapped pairwise judging of judge-oracle tasks.
  Layer 3 — judge calibration against the ground-truth subset.

Pure stdlib; deterministic under the fixed seed (bootstrap uses random.Random(seed),
never the global RNG). Judge calls go through the injectable `chat_fn` so tests run
offline and the runtime wires in the real registry.
"""
import re
from collections import defaultdict

from backend import config

PARITY_PP = 2.0  # pre-registered parity criterion: CI within ±2 percentage points
N_BOOT = 10_000


def _judge_chat(messages: list[dict]) -> str:
    from backend.providers import registry
    return registry.chat(config.JUDGE_MODEL, messages, max_tokens=8, temperature=0.0).text


def _per_task_accuracy(rows: list[dict]) -> dict:
    """(task_id, arm) → mean correct over k repeats, ground-truth rows only."""
    acc = defaultdict(list)
    for r in rows:
        if r["correct"] is not None:
            acc[(r["task_id"], r["arm"])].append(1.0 if r["correct"] else 0.0)
    return {key: sum(v) / len(v) for key, v in acc.items()}


def layer1(rows: list[dict], seed: int = 42, n_boot: int = N_BOOT) -> dict:
    """Paired accuracy delta (B − A, signed — a negative delta is published, not
    hidden) with a paired-bootstrap 95% CI: resample TASK PAIRS with replacement
    so per-task difficulty stays coupled between arms."""
    acc = _per_task_accuracy(rows)
    task_ids = sorted({t for (t, arm) in acc if (t, "a") in acc and (t, "b") in acc})
    if not task_ids:
        return {"skipped": "no paired ground-truth tasks"}

    deltas = [acc[(t, "b")] - acc[(t, "a")] for t in task_ids]
    acc_a = sum(acc[(t, "a")] for t in task_ids) / len(task_ids)
    acc_b = sum(acc[(t, "b")] for t in task_ids) / len(task_ids)

    import random
    rng = random.Random(seed)
    n = len(deltas)
    boot = sorted(sum(deltas[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    ci = [round(boot[int(0.025 * n_boot)] * 100, 2), round(boot[int(0.975 * n_boot)] * 100, 2)]

    return {
        "acc_a": round(acc_a, 4), "acc_b": round(acc_b, 4),
        "delta_pp": round((acc_b - acc_a) * 100, 2),
        "ci95_pp": ci, "n_tasks": n, "seed": seed,
    }


def per_tier(rows: list[dict]) -> list[dict]:
    """Accuracy delta grouped by the tier arm B actually used — the direct proof
    the router only keeps a query small when small is sufficient."""
    acc = _per_task_accuracy(rows)
    tier_of = {}
    for r in rows:
        if r["arm"] == "b" and r["tier"]:
            tier_of.setdefault(r["task_id"], r["tier"])
    grouped = defaultdict(list)
    for t, tier in tier_of.items():
        if (t, "a") in acc and (t, "b") in acc:
            grouped[tier].append(acc[(t, "b")] - acc[(t, "a")])
    return [{"tier": tier, "n": len(d), "delta_pp": round(sum(d) / len(d) * 100, 2)}
            for tier, d in sorted(grouped.items())]


def _pairwise_verdict(prompt: str, ans1: str, ans2: str, reference: str, chat_fn) -> str:
    """One blind comparison → '1' | '2' | 'tie'. The judge never learns which arm
    produced which answer (no brand bias)."""
    msg = (f"Two answers to the same question. Judge which is better and correct.\n\n"
           f"Question: {prompt}\n\nReference answer: {reference}\n\n"
           f"Answer 1: {ans1}\n\nAnswer 2: {ans2}\n\n"
           f"Reply with exactly one token: 1, 2, or tie.")
    raw = chat_fn([{"role": "user", "content": msg}]).strip().lower()
    m = re.search(r"\b(1|2|tie)\b", raw)
    return m.group(1) if m else "tie"  # unparseable verdict = no information = tie


def layer2(rows: list[dict], tasks: list[dict], chat_fn=None) -> dict:
    """Blind pairwise judging with position-swapped double judging: every pair is
    judged twice with answer order flipped; verdicts that follow the position
    (rather than the answer) are recorded as ties. Flip rate >20% demotes the
    whole layer to inconclusive rather than keeping a position-biased result."""
    chat_fn = chat_fn or _judge_chat
    by_key = {(r["task_id"], r["arm"]): r for r in rows if r["k_index"] == 0 and r["answer"]}
    wins = ties = losses = flips = judged = 0

    for task in tasks:
        if task["oracle"]["type"] != "judge":
            continue
        a = by_key.get((task["id"], "a"))
        b = by_key.get((task["id"], "b"))
        if not a or not b:
            continue
        judged += 1
        ref = task["oracle"]["reference"]
        # Round 1: slot1=B, slot2=A.  Round 2: swapped.
        v1 = _pairwise_verdict(task["prompt"], b["answer"], a["answer"], ref, chat_fn)
        v2 = _pairwise_verdict(task["prompt"], a["answer"], b["answer"], ref, chat_fn)
        b_wins_r1, b_wins_r2 = v1 == "1", v2 == "2"
        a_wins_r1, a_wins_r2 = v1 == "2", v2 == "1"
        if b_wins_r1 and b_wins_r2:
            wins += 1
        elif a_wins_r1 and a_wins_r2:
            losses += 1
        else:
            ties += 1
            if v1 != "tie" and v2 != "tie":  # both decisive but contradictory = position-driven
                flips += 1

    flip_rate = flips / judged if judged else 0.0
    return {
        "wins_b": wins, "ties": ties, "losses_b": losses,
        "position_flips": flips, "n_judged": judged,
        "inconclusive": flip_rate > 0.20,
    }


def layer3(rows: list[dict], tasks: list[dict], chat_fn=None, cap: int = 40) -> dict:
    """Judge calibration: on tasks where ground truth exists, ask the judge to
    grade arm B's answer and compare with the oracle. Publishes the judge's own
    error rate — especially false passes, the failure mode that would hide
    quality loss (KR3.4)."""
    chat_fn = chat_fn or _judge_chat
    task_by_id = {t["id"]: t for t in tasks}
    agree = total = false_pass = actually_wrong = 0

    for r in rows:
        if total >= cap:
            break
        if r["arm"] != "b" or r["k_index"] != 0 or r["correct"] is None or not r["answer"]:
            continue
        task = task_by_id.get(r["task_id"])
        if not task:
            continue
        msg = (f"Question: {task['prompt']}\n\nAnswer: {r['answer']}\n\n"
               f"Is this answer correct? Reply with exactly one token: yes or no.")
        raw = chat_fn([{"role": "user", "content": msg}]).strip().lower()
        judged_correct = raw.startswith("y")
        total += 1
        if judged_correct == bool(r["correct"]):
            agree += 1
        if not r["correct"]:
            actually_wrong += 1
            if judged_correct:
                false_pass += 1

    return {
        "judge_agreement_pct": round(100 * agree / total, 1) if total else None,
        "judge_false_pass_pct": round(100 * false_pass / actually_wrong, 1) if actually_wrong else 0.0,
        "n_checked": total,
    }


def evaluate(rows: list[dict], tasks: list[dict], k: int, chat_fn=None,
             seed: int = 42, with_judge_layers: bool = True) -> dict:
    """The full spec-09 evaluation block. Judge layers degrade gracefully: if the
    judge is unreachable (no key, offline), layers 2/3 report why they were
    skipped instead of failing the whole report — parity_met needs only layer 1."""
    l1 = layer1(rows, seed=seed)
    result = {
        "layer1": {**l1, "k": k},
        "per_tier": per_tier(rows),
        "parity_criterion": f"CI within ±{PARITY_PP}pp",
        "parity_met": (
            "ci95_pp" in l1
            and l1["ci95_pp"][0] >= -PARITY_PP and l1["ci95_pp"][1] <= PARITY_PP
        ),
    }
    if with_judge_layers:
        try:
            result["layer2"] = layer2(rows, tasks, chat_fn=chat_fn)
            result["layer3"] = layer3(rows, tasks, chat_fn=chat_fn)
        except Exception as e:
            result["layer2"] = result["layer3"] = {"skipped": f"judge unavailable: {e}"[:200]}
    else:
        result["layer2"] = result["layer3"] = {"skipped": "judge layers disabled"}
    return result
