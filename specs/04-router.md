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

Two verification paths, chosen by tier — a deliberate hybrid, not a uniform policy
(D19). The independent judge is the more rigorous, more expensive check; the
self-confidence gate is free but only trusted where the cost of being wrong is
smallest.

```python
def check_confidence(chat_result: ChatResult) -> dict:
    # → {"score": float, "pass": bool, "method": "self_confidence", "raw": ...}
```
- **Trivial tier only.** No second model call — the trust signal rides free on the
  answering call itself.
- Score = geometric-mean token probability of the generated answer:
  `exp(mean(token_logprob for token in completion))`, requested via the
  provider's `logprobs=True` (OpenAI-compatible wire protocol; Groq/OpenAI/Gemini
  support this, Anthropic does not — irrelevant here since trivial never routes to
  Anthropic).
  `pass = score >= config.CONFIDENCE_FLOOR` (default 0.80, tuned on the 20-query
  dry run alongside `QUALITY_FLOOR`, spec 05).
- **Why not trust this at moderate/hard**: token-level confidence measures how
  *predictable* the tokens were, not whether the content is *correct* — a model can
  be fluently, confidently wrong. Acceptable risk at trivial (cheap to be wrong,
  cheap to retry); not acceptable once a wrong answer means either shipping a bad
  answer or an expensive unnecessary hop to Opus.
- **Fallback**: if the resolved trivial model doesn't support `logprobs` (e.g. a
  provider override without the OpenAI-compatible wire protocol), fall back to
  `verify()` (independent judge) for that call — safe direction, never silently
  skip verification.

```python
def verify(query: str, answer: str) -> dict:
    # → {"score": float, "pass": bool, "judge_model": str,
    #    "judge_impact": measure-record, "raw": str}
```
- **Moderate tier only** (hard is exempt — Opus is the parity target, nothing above
  it to judge against).
- Judge = `config.JUDGE_MODEL` (Gemini Flash — independent family, D9). If its key
  is unavailable → fallback: judge one tier above the answering model.
- Prompt: rubric scoring 0–1 on correctness, completeness, instruction-following;
  answer strictly as JSON `{"score": 0.87}`. One strict-format retry on parse
  failure; still unparseable → treated as fail (safe direction: escalate).
- `pass = score >= config.QUALITY_FLOOR` (default 0.85, tuned on the 20-query dry
  run, spec 05).
- Judge impact is measured and returned so `route()` books it against Ember (D4).
- **Why keep the judge here and not fold moderate into the free confidence gate
  too**: per `data/energy_factors.json`, the judge model's own footprint
  (`wh_per_1k_out: 0.3`) is *larger* per token than the trivial model it would
  otherwise be grading (`wh_per_1k_out: 0.12`) — cutting the judge at trivial tier
  removes a cost that was arguably bigger than the answer itself. Moderate-tier
  answers are the ones that, if wrong, actually cost real quality or an expensive
  escalation, so the independent check stays there.

### `route.py`
```python
def route(query: str) -> dict
```
Orchestrates: classify → pick_zone → answer with `ladder[tier]` →
- `tier == "trivial"` → `check_confidence` (no second call)
- `tier == "moderate"` → `verify` (independent judge call)
- `tier == "hard"` → skip entirely, Opus is the parity target

→ on fail escalate ONE tier and repeat (max 2 hops, hard stop at Opus) → return
`{answer, tier_first, tier_final, escalations: [...], calls: [impact-record, ...],
totals: {gco2, cost_usd, wh, latency_ms}}`.
**Totals sum every call made — classifier, answers, judges — nothing hidden.** A
trivial-tier pass therefore contributes exactly one call to `calls[]`; only a
moderate-tier check or a trivial-tier escalation adds a second.

## Escalation invariants

- Monotonic ladder, one rung per hop, ≤2 hops → termination guaranteed.
- Every escalation logged with the failing score (confidence score at trivial,
  judge score at moderate); the dashboard shows the rate per tier (healthy band
  ~10–30%; it's a feature, proof the gate works, not a bug).
- Worst case cost: failed trivial attempt (no judge) + failed moderate attempt +
  judge + Opus call — slightly more than baseline for that query, but the answer is
  never worse. Parity by construction *from moderate tier up*; trivial tier trades
  a small, bounded risk (self-confidence can be wrong) for cutting the single
  costliest fixed overhead in the whole pipeline.

## Edge cases

- Trivial model doesn't support `logprobs` → fall back to `verify()` (independent
  judge) for that call, logged as a fallback — never silently skip verification.
- Confidence score parses as `NaN`/missing (e.g. empty completion) → treated as
  fail (safe direction: escalate to moderate).
- Judge unavailable mid-run (key dies, 429 storm) → fallback judge strategy, logged;
  never accept a moderate-tier answer unjudged.
- Judge scores an Opus escalation's answer low → irrelevant: Opus answers are
  accepted as the parity target by definition.
- Classifier tie/ambiguity → round up (safer for quality, gate protects savings).
- Empty/whitespace query → 400 at the API layer, never reaches the ladder.

## Acceptance criteria

- `route("What is 2+2?")` answers from the trivial tier via `check_confidence`
  only — `calls` has exactly one entry, no judge call present.
- A trivial-tier answer with deliberately low confidence (e.g. mocked low
  logprobs) escalates to moderate, where `verify()` runs as normal.
- A deliberately hard prompt (multi-step proof) escalates at least once and lands
  on Opus, with every hop's impact in `calls`.
- Sum of `calls` impact == `totals` exactly.
- With `QUALITY_FLOOR=1.01` (force-fail) and `CONFIDENCE_FLOOR=1.01`, every query
  walks the full ladder and stops at Opus — no infinite loops.
