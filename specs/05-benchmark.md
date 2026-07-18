# 05 — Benchmark Harness (`backend/benchmark/`)

The A/B test that produces the headline number: **"−X% CO₂ (est.) · accuracy within
Y% of all-Opus · −Z% cost (exact)."** Identical inputs, both arms, everything counted.

## Arms

- **Arm A (baseline):** every query → `MODEL_HARD` (latest Opus), `BASELINE_ZONE`.
- **Arm B (Ember):** `route()` — right-sizing + gate + simulated greenest zone.

## Files & contracts

### `workloads.py`
`load(name="default") → list[Task]` from `data/workloads/*.json`:
```json
{"id": "gsm8k-017", "category": "math", "prompt": "...",
 "oracle": {"type": "numeric_exact", "answer": "42"}}
```
~150 tasks. Categories & oracles:
| Category | ~Count | Oracle | Provenance |
|---|---|---|---|
| trivial QA / formatting | 50 | `string_match` / judge | hand-written, in-repo |
| math | 40 | `numeric_exact` (parse final number) | GSM8K test subset |
| light reasoning | 40 | judge vs reference answer | hand-written + adapted |
| code | 20 | `unit_test` (run against asserts, subprocess, 5 s timeout) | hand-written |

### `harness.py`
`run(workload, k=3, limit=None, assume_yes=False, resume=None) → run_id`

> **Contract note for P2:** each entry of `route()`'s `calls[]` must carry
> `"role"` (`answer|classifier|judge`) and `"tier"` alongside the `measure()`
> record — the harness persists one row per call and D4 auditability needs the
> role. The harness defensively defaults a missing role (final call → `answer`,
> others → `judge`) but that's a fallback, not the contract.
- **Interleaved** A,B,A,B per task (D14) — no arm-level batching.
- Bounded concurrency `MAX_CONCURRENCY` (~4), exponential backoff on 429.
- **Resumable:** every result committed to SQLite immediately; restart continues
  from the last completed (run_id, task, arm, k) tuple.
- Prints an up-front spend estimate (Opus calls × price table) before starting.
- Failed/timeout calls stay in the totals (cost + energy of the attempt).

### `scoring.py`
`score(task, answer) → {"correct": bool, "score": float, "oracle": str}` per oracle
type. Judge-scored categories use `JUDGE_MODEL`; **ground truth wins** where both
exist, and judge-vs-truth disagreement rate is logged (methodology footnote).

### `report.py`
`build(run_id) → dict`, persisted + served by `/report/{id}`:
```json
{"headline": {"co2_reduction_pct": ..., "accuracy_delta_pct": ...,
              "cost_reduction_pct": ..., "latency_p50_ms": {"a":..,"b":..}},
 "per_arm": {"a": {...totals...}, "b": {...totals...}},
 "escalation": {"rate": ..., "by_tier": {...}},
 "sci": {"per_query_gco2": {"a":..,"b":..}, "functional_unit": "one query", "m": 0},
 "extrapolation": {"queries_per_day": 1000000, "tonnes_co2_per_year_saved": ...,
                   "label": "estimated"},
 "labels": {"energy": "estimated", "cost": "exact", "intensity_mode": "live|fallback"}}
```

## Honesty guardrails (encoded, not aspirational)

- Identical inputs both arms; same K; same wall-clock interleaving.
- Arm B totals include classifier + judge + every escalation attempt (D4).
- No query excluded from carbon/cost totals for any reason.
- Escalation rate published in the report and the dashboard.
- Accuracy delta reported signed (B − A), even if negative.

## Tuning protocol (before the full run)

20-query dry run → inspect escalation rate. <10%: floor may be too lax, spot-check
accepted trivial answers. >30%: floor too strict or classifier under-routing.
Adjust `QUALITY_FLOOR` / classifier thresholds; re-dry-run; then full K=3.

## Edge cases

- Credit exhaustion mid-run → resumable; spend estimate up front prevents surprises.
- Opus 429 storms → backoff + concurrency cap; interleaving means partial runs are
  still balanced pairs.
- Code oracle security: subprocess with timeout, no network, workload code is ours.
- Run aborted → partial results queryable; report builder requires matched A/B pairs
  and drops unmatched tail (logged, never silent).

## Acceptance criteria

- `uv run python -m backend.benchmark.harness --limit 10` completes both arms and
  prints the headline line.
- Kill it mid-run, rerun → resumes, no duplicate rows.
- Full run: ~150 × 2 arms × K=3 in <1 h wall-clock within rate limits.
