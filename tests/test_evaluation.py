"""Evaluation statistics (spec 09) — the math behind 'accuracy within Y% of
all-Opus.' Wrong stats here means an indefensible claim on stage; every property
the spec pre-registers (pairing, determinism, position-bias handling, the ±2pp
criterion) gets pinned."""
from backend.benchmark import evaluation


def _row(task_id, arm, correct, tier="trivial", k_index=0, answer="ans"):
    return {"task_id": task_id, "arm": arm, "k_index": k_index, "tier": tier,
            "answer": answer, "score": None, "correct": correct, "error": None,
            "latency_ms": 100.0}


def _paired_rows(pattern):
    """pattern: list of (a_correct, b_correct, tier) per task."""
    rows = []
    for i, (a, b, tier) in enumerate(pattern):
        rows.append(_row(f"t{i}", "a", a, tier))
        rows.append(_row(f"t{i}", "b", b, tier))
    return rows


def test_layer1_delta_hand_computed():
    """4 tasks: A correct on all, B correct on 3 → delta = −25pp exactly, signed
    and negative — spec 09 explicitly forbids hiding a negative delta."""
    rows = _paired_rows([(True, True, "trivial")] * 3 + [(True, False, "moderate")])
    l1 = evaluation.layer1(rows, n_boot=500)
    assert l1["acc_a"] == 1.0 and l1["acc_b"] == 0.75
    assert l1["delta_pp"] == -25.0


def test_bootstrap_is_deterministic_under_seed():
    """Spec 09 acceptance: the CI must be reproducible (fixed seed) — a report
    rebuilt for the judges must show the same interval, or the number looks
    made up."""
    rows = _paired_rows([(True, True, "trivial"), (True, False, "moderate"),
                         (False, True, "hard"), (True, True, "trivial")])
    a = evaluation.layer1(rows, seed=42, n_boot=1000)
    b = evaluation.layer1(rows, seed=42, n_boot=1000)
    assert a["ci95_pp"] == b["ci95_pp"]


def test_ci_contains_point_estimate():
    """Basic sanity a stats-literate judge would check first: the 95% interval
    must bracket the point estimate."""
    rows = _paired_rows([(True, False, "trivial"), (True, True, "moderate"),
                         (False, False, "hard"), (True, True, "trivial")])
    l1 = evaluation.layer1(rows, n_boot=1000)
    assert l1["ci95_pp"][0] <= l1["delta_pp"] <= l1["ci95_pp"][1]


def test_parity_criterion_is_the_ci_not_the_point():
    """The pre-registered claim (±2pp) applies to the whole CI. Perfect parity →
    met; a clear 25pp gap → not met, no matter how the point estimate is spun."""
    perfect = evaluation.evaluate(_paired_rows([(True, True, "trivial")] * 6),
                                  tasks=[], k=1, with_judge_layers=False)
    assert perfect["parity_met"] is True

    gap = evaluation.evaluate(_paired_rows([(True, False, "trivial")] * 2
                                           + [(True, True, "trivial")] * 6),
                              tasks=[], k=1, with_judge_layers=False)
    assert gap["parity_met"] is False


def test_per_tier_breakdown_groups_by_arm_b_tier():
    """The per-tier delta is the D19 safety net: it must group by the tier arm B
    actually answered from, so a parity failure at the trivial tier (confidence
    gate too lax) is visible instead of averaged away."""
    rows = _paired_rows([(True, True, "trivial"), (True, False, "trivial"),
                         (True, True, "hard")])
    tiers = {t["tier"]: t for t in evaluation.per_tier(rows)}
    assert tiers["trivial"]["n"] == 2 and tiers["trivial"]["delta_pp"] == -50.0
    assert tiers["hard"]["delta_pp"] == 0.0


# --- Layer 2: blind position-swapped pairwise judging -----------------------------

TASKS = [{"id": "t0", "category": "reasoning", "prompt": "why?",
          "oracle": {"type": "judge", "reference": "because"}}]


def _rows_with_answers(a_text, b_text):
    return [_row("t0", "a", None, answer=a_text), _row("t0", "b", None, answer=b_text)]


def test_layer2_consistent_verdict_counts_as_win():
    """A judge that prefers B's answer in BOTH orderings is a real win. The fake
    judge here picks by content ('GOOD' beats 'BAD'), not position — the honest
    case the design must reward."""
    def content_judge(messages):
        text = messages[0]["content"]
        return "1" if text.index("GOOD") < text.index("BAD") else "2"

    l2 = evaluation.layer2(_rows_with_answers("BAD", "GOOD"), TASKS, chat_fn=content_judge)
    assert (l2["wins_b"], l2["losses_b"], l2["ties"]) == (1, 0, 0)
    assert l2["inconclusive"] is False


def test_layer2_position_bias_becomes_tie_and_flags_inconclusive():
    """THE anti-bias mechanism (spec 09): a judge that always says 'Answer 1'
    is following position, not content. Swapped judging must convert that to a
    tie, count the flip, and — at >20% flip rate — demote the layer to
    inconclusive rather than report position noise as wins."""
    l2 = evaluation.layer2(_rows_with_answers("x", "y"), TASKS, chat_fn=lambda m: "1")
    assert (l2["wins_b"], l2["losses_b"], l2["ties"]) == (0, 0, 1)
    assert l2["position_flips"] == 1 and l2["inconclusive"] is True


def test_layer2_unparseable_verdict_is_a_tie():
    """A rambling judge reply with no clear 1/2/tie carries no information —
    it must count as a tie, never crash and never default to a win."""
    l2 = evaluation.layer2(_rows_with_answers("x", "y"), TASKS,
                           chat_fn=lambda m: "well, both have merit...")
    assert l2["ties"] == 1


# --- Layer 3: judge calibration ---------------------------------------------------

def test_layer3_false_pass_rate_exposes_gullible_judge():
    """KR3.4: the judge's own error rate is published. A judge that says 'yes' to
    everything must show 100% false-pass on the wrong answers — this number is
    what tells judges (human ones) how much to trust the quality gate."""
    tasks = [{"id": f"t{i}", "category": "trivial", "prompt": "q",
              "oracle": {"type": "numeric_exact", "answer": "1"}} for i in range(4)]
    rows = [_row("t0", "b", True), _row("t1", "b", True),
            _row("t2", "b", False), _row("t3", "b", False)]
    l3 = evaluation.layer3(rows, tasks, chat_fn=lambda m: "yes")
    assert l3["judge_agreement_pct"] == 50.0
    assert l3["judge_false_pass_pct"] == 100.0


def test_judge_layers_degrade_gracefully_offline():
    """parity_met must be computable with no keys and no network (layer 1 is
    ground truth) — the judge layers report why they were skipped instead of
    taking the whole report down (D18 offline-first)."""
    def dead_judge(messages):
        raise RuntimeError("no API key")

    result = evaluation.evaluate(_paired_rows([(True, True, "trivial")] * 4),
                                 tasks=TASKS, k=1, chat_fn=dead_judge)
    assert result["parity_met"] is True
    assert "skipped" in result["layer2"]
