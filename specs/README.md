# Ember Specs

One document per technical domain. Each spec owns its module's file contracts,
edge cases, and acceptance criteria — a workstream (or teammate) adopts a spec,
not the whole project. `00` and `01` are shared context everyone reads first.

| # | Spec | Owns | Status |
|---|---|---|---|
| 00 | [Overview & decisions](00-overview.md) | Concept, prize strategy, locked decision sheet D1–D18, open items | ✅ locked |
| 01 | [Architecture](01-architecture.md) | System topology, repo layout, request lifecycle, config | ✅ locked |
| 02 | [Providers](02-providers.md) | `backend/providers/` — uniform multi-vendor client layer | ✅ built |
| 03 | [Measurement](03-measurement.md) | `backend/measurement/` — energy, carbon, cost, labels, SCI | ✅ built |
| 04 | [Router & quality gate](04-router.md) | `backend/router/` — classifier, selector, judge, escalation | 🔨 next |
| 05 | [Benchmark harness](05-benchmark.md) | `backend/benchmark/` — workloads, A/B runner, scoring, report | ⬜ |
| 06 | [API & database](06-api-db.md) | `backend/app.py`, `backend/db/` — endpoint + schema contracts | ⬜ |
| 07 | [Dashboard](07-dashboard.md) | `dashboard/` — views, polling, mock contract, replay mode | ⬜ |
| 08 | [Build plan & demo](08-build-plan.md) | 36-hour tracks, demo script, risks | ✅ locked |
| 09 | [Evaluation](09-evaluation.md) | Quantifying Ember-vs-all-Opus performance: paired stats, blind judging, parity criterion | ✅ locked |

Rule: when code and spec disagree, fix one of them in the same commit —
never let them drift silently.
