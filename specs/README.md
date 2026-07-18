# Ember Specs

One document per technical domain. Each spec owns its module's file contracts,
edge cases, and acceptance criteria — a workstream (or teammate) adopts a spec,
not the whole project. `00` and `01` are shared context everyone reads first.

Start with the visual map: [`../OVERVIEW.md`](../OVERVIEW.md) — diagrams, objectives,
and the 4-person delegation (P1–P4 below).

| # | Spec | Owns | Owner | Status |
|---|---|---|---|---|
| 00 | [Overview & decisions](00-overview.md) | Concept, prize strategy, locked decision sheet D1–D18, open items | all | ✅ locked |
| 01 | [Architecture](01-architecture.md) | System topology, repo layout, request lifecycle, config | all | ✅ locked |
| 02 | [Providers](02-providers.md) | `backend/providers/` — uniform multi-vendor client layer | P2 | ✅ built |
| 03 | [Measurement](03-measurement.md) | `backend/measurement/` — energy, carbon, cost, labels, SCI | P1 | ✅ built |
| 04 | [Router & quality gate](04-router.md) | `backend/router/` — classifier, selector, judge, escalation | P2 | 🔨 next |
| 05 | [Benchmark harness](05-benchmark.md) | `backend/benchmark/` — workloads, A/B runner, scoring, report | P3 | ✅ built (live run awaits P2's `route()` + keys) |
| 06 | [Storage & events](06-storage.md) | `backend/db/` — SQLite schema + the event-stream contract | P1 | ✅ built (by P3, per frozen contract) |
| 07 | [CLI & report](07-cli.md) | `backend/cli.py`, `tui/`, `report_html.py` — commands, race TUI, HTML artifact, MCP stretch | P4 | 🔨 partial |
| 08 | [Build plan & demo](08-build-plan.md) | 36-hour tracks, demo script, risks | P4 | ✅ locked |
| 09 | [Evaluation](09-evaluation.md) | Quantifying Ember-vs-all-Opus performance: paired stats, blind judging, parity criterion | P3 | ✅ built |
| 10 | [OKRs](10-okrs.md) | Objectives + measurable key results, owners, verification commands, cut-line discipline | all | ✅ locked |

## Per-person task lists (`tasks/`)

Sequenced milestones with commands and checks — your day-to-day checklist:
[P1 backend core](tasks/P1-backend-core.md) ·
[P2 router & providers](tasks/P2-router-providers.md) ·
[P3 benchmark & evaluation](tasks/P3-benchmark-evaluation.md) ·
[P4 CLI race view & demo](tasks/P4-cli-demo.md)

All module stubs exist in the repo with their contracts in the docstring — grep
your initials: `grep -rn "P2 owns" backend/`.

Rule: when code and spec disagree, fix one of them in the same commit —
never let them drift silently.
