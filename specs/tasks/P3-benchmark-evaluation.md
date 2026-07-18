# P3 — Benchmark & Evaluation (specs 05, 09 · KRs 1.2, 1.3, 2.x, 3.4)

Read first: OVERVIEW.md, specs 00, 01. You own the proof: the harness that produces
the headline number and the statistics that make "parity with Opus" defensible.
Most self-contained track — everything testable with `--limit 10`.

## M1 — Workloads (h2–8) — spec 05 `workloads.py` + `data/workloads/`
- [ ] Schema per spec 05: `{id, category, prompt, oracle:{type, ...}}`.
- [ ] ~50 trivial QA/formatting (hand-write; make them REAL product-shaped queries:
      reformat, extract, one-fact QA, casing, short summaries).
- [ ] ~40 math from GSM8K test split (copy subset into
      `data/workloads/default.json`; cite provenance in a `_source` field).
      Oracle `numeric_exact` (parse last number in answer; strip commas/$).
- [ ] ~40 light reasoning w/ reference answers (hand-write + adapt) — oracle `judge`.
- [ ] ~20 code tasks with asserts — oracle `unit_test` (subprocess, 5 s timeout,
      no network).
- [ ] Check: `workloads.load()` returns ~150 validated tasks; category counts printed.

## M2 — Harness (h8–14) — spec 05 `harness.py` — KR1.2
- [ ] Interleave A,B per task; K=3; bounded concurrency `MAX_CONCURRENCY` with
      exponential backoff on 429 (1s→2s→4s→8s, max 5 tries).
- [ ] Arm A = one `registry.chat(MODEL_HARD, ...)` call, `BASELINE_ZONE`.
      Arm B = P2's `route()`.
- [ ] Per-call rows committed to SQLite immediately via P1's `store.record_call`
      (resume = skip completed (run_id, task, arm, k) tuples).
- [ ] Up-front spend estimate printed + confirmed before any Opus call.
- [ ] Failed/timeout calls stay in totals; task marked incorrect for that repeat.
- [ ] Check: `--limit 10` completes; kill mid-run, rerun → resumes, row count sane.

## M3 — Scoring + report (h14–18) — spec 05 `scoring.py`, `report.py`
- [ ] Oracles: `numeric_exact`, `string_match`, `unit_test`, `judge` (vs reference).
      Ground truth wins over judge where both exist; log disagreement rate.
- [ ] `report.py` builds the spec-05 JSON (headline, per_arm, escalation, sci,
      extrapolation, labels) and persists via P1's Report table.
- [ ] Check: report from a `--limit 10` run renders sane numbers.

## M4 — Evaluation statistics (h18–24) — spec 09 — KR1.3, KR3.4
- [ ] `evaluation.py`: Layer 1 paired accuracy delta + **paired bootstrap 95% CI**
      (10,000 resamples, fixed seed, pure stdlib `random.Random(42)`).
- [ ] Layer 2: blind pairwise judging, **position-swapped double judging**, flips
      → ties; >20% flip rate demotes layer 2 to "inconclusive".
- [ ] Layer 3: judge agreement % + false-pass % vs ground-truth subset.
- [ ] Per-tier delta breakdown; `parity_met` = CI within ±2 pp (pre-registered).
- [ ] Check: evaluation block appears in the report; deterministic under the seed.

## M5 — The real run (h20–26) — with P2's tuned floor
- [ ] 20-task dry run → tune floor with P2 (their M6).
- [ ] Full run: 150 × 2 × K=3. Watch rate limits. Verify headline + parity_met.
- [ ] Freeze: tag the run_id in specs/10-okrs.md tick-boxes; hand run_id to P4.
