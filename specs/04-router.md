# 04 — Router & Quality Gate (`backend/router/`) — 🔨 next up

Picks the smallest sufficient model and the greenest placement, and **guarantees
parity with the all-Opus baseline** via the quality gate. This module is why the
savings number is believable.

## Files & contracts

### `classifier.py`
```python
def classify(query: str) -> dict:
    # → {"tier": "trivial"|"moderate"|"hard", "signals": {...}, "latency_ms": float}
```
- Stage 1 — heuristics (free, instant): length, math/code/reasoning keyword hits,
  question-structure signals, requested-output complexity.
- Stage 2 — only when heuristics are unsure: one call to the trivial-tier model,
  "rate difficulty 1–3", strict format, `max_tokens=4`, counted as overhead (D4).
- Budget: <300 ms typical. Misclassification is SAFE: under-routing is caught by the
  gate (costs tokens, not quality); over-routing costs savings only.

### `selector.py`
```python
def pick_zone() -> dict   # greenest_zone() + label "simulated placement"
```
Thin wrapper over `carbon.greenest_zone()` recording both the simulated pick and
`BASELINE_ZONE` so the calculator can attribute each arm (D3/D5).

### `quality_gate.py`
```python
def verify(query: str, answer: str) -> dict:
    # → {"score": float, "pass": bool, "judge_model": str,
    #    "judge_impact": measure-record, "raw": str}
```
- Judge = `config.JUDGE_MODEL` (Gemini Flash — independent family, D9). If its key
  is unavailable → fallback: judge one tier above the answering model.
- Prompt: rubric scoring 0–1 on correctness, completeness, instruction-following;
  answer strictly as JSON `{"score": 0.87}`. One strict-format retry on parse
  failure; still unparseable → treated as fail (safe direction: escalate).
- `pass = score >= config.QUALITY_FLOOR` (default 0.85, tuned on the 20-query dry
  run, spec 05).
- Judge impact is measured and returned so `route()` books it against Ember (D4).

### `route.py`
```python
def route(query: str) -> dict
```
Orchestrates: classify → pick_zone → answer with `ladder[tier]` → verify (skip when
tier == hard: Opus is the parity target, nothing above it) → on fail escalate ONE
tier and repeat (max 2 hops, hard stop at Opus) → return
`{answer, tier_first, tier_final, escalations: [...], calls: [impact-record, ...],
totals: {gco2, cost_usd, wh, latency_ms}}`.
**Totals sum every call made — classifier, answers, judges — nothing hidden.**

## Escalation invariants

- Monotonic ladder, one rung per hop, ≤2 hops → termination guaranteed.
- Every escalation logged with the failing score; the dashboard shows the rate
  (healthy band ~10–30%; it's a feature, proof the gate works, not a bug).
- Worst case cost: failed small attempt + judge + Opus call — slightly more than
  baseline for that query, but the answer is never worse. Parity by construction.

## Edge cases

- Judge unavailable mid-run (key dies, 429 storm) → fallback judge strategy, logged;
  never accept a non-frontier answer unjudged.
- Judge scores an Opus escalation's answer low → irrelevant: Opus answers are
  accepted as the parity target by definition.
- Classifier tie/ambiguity → round up (safer for quality, gate protects savings).
- Empty/whitespace query → 400 at the API layer, never reaches the ladder.

## Acceptance criteria

- `route("What is 2+2?")` answers from the trivial tier with a passing verdict.
- A deliberately hard prompt (multi-step proof) escalates at least once and lands
  on Opus, with every hop's impact in `calls`.
- Sum of `calls` impact == `totals` exactly.
- With `QUALITY_FLOOR=1.01` (force-fail), every query walks the full ladder and
  stops at Opus — no infinite loops.
