# 10 — OKRs

Objectives and measurable key results for the 36-hour build. Every KR has an owner
and a verification command/action — a KR that can't be checked doesn't count.
Status boxes get ticked in this file as they land (spec-code lockstep rule).

## O1 — Prove frontier-parity routing works
*The quality gate + escalation genuinely holds Opus-level output.*

| KR | Target | Owner | Verified by |
|---|---|---|---|
| KR1.1 | `route()` passes all spec-04 acceptance tests (trivial stays small, hard escalates to Opus, forced-fail floor walks full ladder, totals == sum of calls) | P2 | `uv run python -m backend.router.route_test` |
| KR1.2 | Full benchmark completes: 150 tasks × 2 arms × K=3, resumable, <1 h | P3 | `uv run python -m backend.benchmark.harness` |
| KR1.3 | Accuracy delta 95% CI within **±2 pp** of all-Opus (pre-registered, spec 09) | P3 | `evaluation` block in `/report/{id}` shows `parity_met: true` |
| KR1.4 | Escalation rate in the 10–30% healthy band after floor tuning | P2+P3 | report `escalation.rate` |

## O2 — Quantified savings
*The headline number, produced honestly.*

| KR | Target | Owner | Verified by |
|---|---|---|---|
| KR2.1 | Cost reduction vs all-Opus ≥ **60%** (exact, price-sheet math, D4 overhead included) | P3 | report `headline.cost_reduction_pct` |
| KR2.2 | CO₂ reduction vs all-Opus ≥ **40%** (estimated, labeled) | P3 | report `headline.co2_reduction_pct` |
| KR2.3 | Latency p50 of Ember ≤ baseline ("and it's faster") | P3 | report `headline.latency_p50_ms` |
| KR2.4 | One command produces the headline line | P3 | spec-00 success criterion 1 |

## O3 — Audit-grade transparency (the Deloitte 30%)

| KR | Target | Owner | Verified by |
|---|---|---|---|
| KR3.1 | Methodology view renders 100% of energy factors with source + `params_known` flag | P1+P4 | open view, count rows vs `energy_factors.json` |
| KR3.2 | Every number in the UI carries a provenance label (`estimated/exact/live/cached/snapshot/fallback/replay`) | P4 | spec-07 acceptance sweep |
| KR3.3 | Factor/price v0 values verified against EcoLogits + provider price pages, sources updated | P1 | data-file `source` fields cite checked URLs/dates |
| KR3.4 | Judge calibration published (agreement % + false-pass % vs ground truth) | P3 | report `evaluation.layer3` |

## O4 — Win-ready demo

| KR | Target | Owner | Verified by |
|---|---|---|---|
| KR4.1 | Airplane-mode test: all four views render with Wi-Fi off after server restart | P1+P4 | do it, hour 26–32 |
| KR4.2 | Demo script rehearsed ×2, timed **under 4 minutes** | P4 (drives), all | stopwatch, hour 32–36 |
| KR4.3 | Repo public, README + OVERVIEW current, specs match code | all | reviewer skim at freeze |
| KR4.4 | Live race view runs on real benchmark events, replay tag honest when offline | P4 | spec-07 acceptance |

## Cut-line discipline

If behind at **h20**: cut stretch (leaderboard/SDK) first, then reduce K=3→1, then
shrink workload to 100 — in that order. Never cut: the quality gate, the labels,
the methodology view, or the offline demo.
