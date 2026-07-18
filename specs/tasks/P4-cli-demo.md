# P4 — CLI Race View, Report & Demo (specs 07, 08 · KRs 3.2, 4.1, 4.2, 4.4)

Read first: OVERVIEW.md, specs 00, 01, 07. You own everything judges SEE — now a
terminal race + an HTML artifact instead of a web app (pivot decision). No frontend
stack needed: it's all Python. `ember doctor` / `ember methodology` are built —
copy their style.

## M1 — Race view on synthetic events (h0–8) — spec 07
- [ ] `uv sync && uv run ember doctor` — environment works.
- [ ] `backend/tui/race.py` (Textual): two counter pairs (gCO₂ + $), baseline dim
      grey vs Ember ember-orange, big tabular digits — the 2 m readability test.
- [ ] Drive it first from a synthetic event generator (script that emits spec-06
      event dicts on a timer) so you never wait on P1/P3.
- [ ] Smooth counter animation: lerp displayed value toward the latest committed
      value each frame (D16 — smooth AND honest).
- [ ] Progress bar, escalation-rate chip, scrolling event ticker
      (`task · arm · tier badge · gCO₂ · ✓/✗`), provenance tags on every number (KR3.2).
- [ ] `--plain` fallback: same race as Rich line updates, no Textual (TTY insurance).

## M2 — Live + replay wiring (h8–16)
- [ ] Swap synthetic events for `store.get_run_events(run_id, after_seq)` polling
      (0.5–1 s). `status: running` → follow live; `done` or >10 s silent → replay
      stored events under a visible `REPLAY` banner (D18 — never fake liveness).
- [ ] Run picker: no `run_id` arg → latest run from `store.list_runs()`.
- [ ] Integration check with P1+P3 at h14: `ember benchmark --limit 10` in one
      terminal, `ember race` following it live in another.

## M3 — `ember report` + the HTML artifact (h14–22) — spec 07
- [ ] Terminal report: headline line, per-arm table, escalation stats, evaluation
      block (delta + CI — render the CI, not just the point estimate).
- [ ] `--html out.html` via `backend/report_html.py`: ONE self-contained file,
      inline CSS, zero external assets (opens from disk, airplane-proof), sections
      per spec 07, `@media print` clean. This artifact carries the glossiness the
      web dashboard used to — invest here.
- [ ] Extrapolation section clearly labeled `estimated`.

## M4 — Polish + stretch (h22–26)
- [ ] Race view cosmetics: the divergence must be legible without narration.
- [ ] Only if M1–M3 are demo-ready: MCP server stretch (spec 07 §MCP, FastMCP,
      `route_query` + `carbon_report`) — the Claude Desktop moment.

## M5 — Demo (h26–36) — KR4.1, KR4.2
- [ ] Demo mode: one command (`ember race --demo`) drives the scripted flow on the
      frozen run_id.
- [ ] Airplane-mode test with P1 (h26): Wi-Fi off, fresh shell → race replay,
      report, methodology all work.
- [ ] Own the demo script (spec 08): rehearse ×2, stopwatch <4 min, assign speaking
      beats. Terminal font size cranked BEFORE judges arrive.
