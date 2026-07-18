# 09 — Evaluation: Quantifying Ember vs All-Opus Performance

The claim "same performance as the latest Opus" must be a **measured, statistically
defensible number**, not vibes. This spec defines exactly how model performance is
quantified between Ember's routed sub-models (arm B) and using Claude Opus directly
for everything (arm A). It extends spec 05's scoring; the harness emits the raw
data, this defines what we compute and claim from it.

## The core design: paired comparison

Every task is answered by BOTH arms (same prompt, same K repeats). Performance is
always compared **per task pair**, never as two independent averages — pairing
cancels out task difficulty as a confound (a hard task drags both arms equally).
Per pair we record: correct_A, correct_B (or score_A, score_B), and derive
win / tie / loss for B vs A.

## Three measurement layers (strongest evidence first)

### Layer 1 — Ground-truth oracles (objective, no LLM opinion involved)
| Category | Metric |
|---|---|
| math (GSM8K) | exact-match on the parsed final number → accuracy % |
| code | unit tests pass/fail → pass rate % |
| trivial QA/formatting (where deterministic) | string/regex match → accuracy % |

These cover ~⅔ of the workload and are immune to judge bias. **Headline accuracy
delta comes from this layer.**

### Layer 2 — Blind pairwise judging (open-ended tasks)
For reasoning/open-QA tasks with no deterministic oracle:
- The judge (Gemini) sees the prompt + both answers labeled only "Answer 1 /
  Answer 2" — it never knows which arm produced which. **Blind = no brand bias.**
- **Position-swapped double judging:** every pair is judged twice with the answer
  order flipped; verdicts that flip with position are recorded as ties. This
  removes position bias (LLM judges measurably favor the first answer).
- Output per pair: B wins / tie / B loses → win-rate table.
- Note the separation of roles: at *runtime* Gemini gates arm B's answers (spec 04);
  at *evaluation* time it compares both arms blind. Same model, different protocol —
  the benchmark verdicts never feed back into routing.

### Layer 3 — Judge calibration (how much to trust Layer 2)
On the ~⅔ of tasks where ground truth exists, also run the judge and report its
**agreement rate with ground truth** (plus its false-pass rate specifically, since
that's the failure mode that would hide quality loss). This number goes in the
methodology view: "our judge agrees with ground truth N% of the time" — it
quantifies the credibility of Layer 2 and of the runtime quality gate itself.

## Statistics (each explained once, for the team)

- **Accuracy delta:** Δ = acc_B − acc_A on Layer-1 tasks, reported **signed**
  (a negative delta is published, not hidden).
- **95% confidence interval via paired bootstrap:** resample the task pairs with
  replacement 10,000× and recompute Δ each time; the middle 95% of those Δs is the
  CI. (Plain-English: "if the workload had been a different random draw of similar
  tasks, how much could Δ wobble?") Pure numpy-free Python, ~20 lines.
- **Parity criterion (pre-registered, in this file, before the full run):** Ember
  claims parity if the CI for Δ lies within **±2 percentage points**. The demo line
  "accuracy within Y%" uses the CI bound, not the point estimate — the honest
  version of the claim.
- **Why K=3 repeats:** LLMs are nondeterministic even at low temperature; repeats
  let us report mean ± spread per arm instead of a lucky single roll.
- **Win/tie/loss (Layer 2):** reported as raw counts + win rate; parity looks like
  a tie-heavy distribution with wins ≈ losses.

## Per-tier breakdown (the interesting product insight)

Report accuracy delta **per routed tier**: on queries Ember kept at the 8B tier,
what was the delta vs Opus? Per-tier parity is the direct proof that the classifier
+ gate combination only keeps a query small when small is genuinely sufficient.
Also report: escalation rate per category, and accuracy of escalated queries
(should approach 100% of baseline — they ended on the same Opus).

## What we explicitly do NOT claim

- Not "Ember beats Opus" — the claim is *statistical parity at a fraction of the
  cost/carbon*.
- Not parity on every conceivable workload — parity on this stated, provenance-
  documented workload mix; the mix is in the repo and the methodology view.
- Not judge infallibility — Layer 3 publishes the judge's own error rate.

## Report additions (extends spec 05's report.py output)

```json
"evaluation": {
  "layer1": {"acc_a": ..., "acc_b": ..., "delta_pp": ..., "ci95_pp": [lo, hi],
             "n_tasks": ..., "k": 3},
  "layer2": {"wins_b": ..., "ties": ..., "losses_b": ..., "position_flips": ...},
  "layer3": {"judge_agreement_pct": ..., "judge_false_pass_pct": ...},
  "per_tier": [{"tier": "trivial", "n": ..., "delta_pp": ...}, ...],
  "parity_criterion": "CI within ±2pp", "parity_met": true
}
```

## Acceptance criteria

- Evaluation module computes all three layers from a finished run's SQLite rows —
  no re-calling models except Layer-2/3 judging.
- Bootstrap CI is deterministic under a fixed seed (reproducible report).
- Position-swap flip rate is reported; if >20%, Layer-2 conclusions are demoted to
  "inconclusive" in the report rather than silently kept.
- The result card (spec 07) renders `delta_pp` + CI, not just a point estimate.
