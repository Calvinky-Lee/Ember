# 07 — CLI & Report (`backend/cli.py`, `backend/tui/`, `backend/report_html.py`)

The product surface is a CLI (pivot decision, supersedes the earlier web-dashboard
plan). Judges see: a live terminal race, then a crisp self-contained HTML report.
Everything renders from SQLite — offline-first (D18) is automatic.

## Commands

| Command | What it does | Status |
|---|---|---|
| `ember doctor` | keys / Electricity Maps / data-table / ladder health check | ✅ built |
| `ember methodology` | audit trail on demand: factor table verbatim, sources, `params_known` flags, scope, sensitivity (KR3.1) | ✅ built |
| `ember route "…"` | one query through the router; prints answer + impact receipt (tier path, gCO₂ est, $ exact, calls incl. overhead) | wired, needs P2's `route()` |
| `ember benchmark [--limit N] [--k K]` | runs the A/B harness with up-front spend confirm | wired, needs P3's harness |
| `ember race [run_id]` | **the demo centerpiece** — live/replay TUI race view | P4-M1 |
| `ember report [run_id] [--html out.html]` | terminal summary; `--html` writes the self-contained ESG/SCI artifact | P4-M3 |

## `ember race` — Textual TUI (P4-M1/M2)

- Two big counter pairs (gCO₂ + $), tabular figures, baseline in dim grey vs Ember
  in ember-orange — readable from 2 m at the judging table.
- Counters animate smoothly between real per-event values (D16): consume
  `store.get_run_events(run_id, after_seq)` on a 0.5–1 s timer, lerp display values
  between committed data points.
- Below: progress bar (pairs done), escalation-rate chip, scrolling event ticker
  (`task · arm · tier badge · gCO₂ · ✓/✗`).
- Every number carries its provenance tag (`est` / `exact` / `live` / `fallback`).
- **Live vs replay:** if the run is `running`, follow it. If `done` (or no new
  events for >10 s), re-emit stored events on a timer under a visible `REPLAY`
  banner — never fake liveness (D18).
- Fallback for weird terminals: `--plain` renders the same race as Rich line
  updates (no Textual), so a broken TTY can't kill the demo.

## `ember report --html` — the shareable artifact (P4-M3)

Single self-contained HTML file (inline CSS, no external assets — opens from disk,
survives airplane mode): headline stats, per-arm table, escalation stats, the
spec-09 evaluation block (delta + CI, win/tie/loss, judge calibration, per-tier),
SCI framing, methodology appendix rendered from the same data as `ember methodology`,
extrapolation clearly labeled. Print-clean (`@media print`) — "hand this to
compliance." This artifact replaces the web dashboard's glossiness; make it strong.

## MCP server (stretch, after MVP — spec 08 cut-line applies)

`backend/mcp_server.py` via FastMCP exposing `route_query` (answer + carbon receipt)
and `carbon_report`. Framing: **delegation** — an agent hands subtasks to Ember
instead of burning frontier tokens itself. One JSON line installs it in Claude
Desktop/Code. Do not start before `ember race` and `--html` are demo-ready.

## Acceptance criteria

- `uv run ember doctor` and `uv run ember methodology` run keyless today. ✅
- `ember race` animates a `--limit 10` run live, then replays it with the banner
  after completion; Wi-Fi off + rerun → replay works identically.
- `--html` report opens from disk with Wi-Fi off and prints cleanly.
- Result line readable at 2 m; race understandable without narration.
