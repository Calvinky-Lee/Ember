# P4 — Dashboard & Demo (specs 07, 08 · KRs 3.2, 4.1, 4.2, 4.4)

Read first: OVERVIEW.md, specs 00, 01. You own everything judges SEE. Build on
mocks from minute one — you never wait for the backend. Scaffold already in
`dashboard/` (Vite + React + Recharts, mock data wired).

## M1 — Scaffold + race view on mocks (h0–8)
- [ ] `cd dashboard && npm install && npm run dev` — app boots with mocks
      (`VITE_USE_MOCKS=1` is the default until h14).
- [ ] Race view per spec 07: two counter pairs (gCO₂ + $), baseline grey vs Ember
      ember-orange, animating between mock events (requestAnimationFrame lerp
      between polled values — smooth, honest, D16).
- [ ] Progress bar (pairs done), escalation-rate chip, event ticker (task · arm ·
      tier badge · gCO₂ · ✓/✗).
- [ ] Provenance tags on every number (KR3.2): small pill `est` / `exact` /
      `live` / `fallback` / `REPLAY`.
- [ ] Design tokens per spec 07 (warm paper, ember accent, moss good-values,
      tabular numerals). Readable from 2 m — font-size test at the demo table.

## M2 — Result card + methodology (h8–14)
- [ ] Result card: headline stats row, per-arm table, escalation stats,
      `Extrapolate` toggle (1M queries/day → t CO₂/yr, `est` label).
      Renders delta + CI, not just a point estimate (spec 09 dep).
- [ ] Methodology view: impact-chain diagram, factor table rendered from
      `/meta/methodology` verbatim (`params_known: false` rows visibly flagged),
      scope statement, sensitivity note. Must read like an audit document.
- [ ] At the h8 sync: confirm your mock JSON matches P1's frozen endpoint shapes
      byte-for-byte (`dashboard/src/mocks/` is the contract test).

## M3 — Real wiring + report (h14–20)
- [ ] `usePoll(runId)`: 1 s interval, `?after_seq` cursor, stops on `done`,
      `stale` flag (>5 s silent) flips to replay-from-store.
- [ ] Flip `VITE_USE_MOCKS=0` against P1's live server; run a `--limit 10`
      benchmark with P3 and watch the race view move on real events.
- [ ] ESG/SCI report view + `@media print` stylesheet ("hand this to compliance").

## M4 — Replay mode + charts (h20–26) — KR4.4
- [ ] Replay: finished run's events re-emitted on a timer, visible `REPLAY` tag.
      Auto-replay when network is down. Never fake liveness (D18).
- [ ] Recharts: per-category savings bar chart + cumulative gCO₂ line (two arms)
      from the real run.

## M5 — Demo (h26–36) — KR4.1, KR4.2
- [ ] Demo mode: one keypress starts the scripted flow on the frozen run_id.
- [ ] Airplane-mode test with P1 (h26): Wi-Fi off, server restart, all views render.
- [ ] Own the demo script (spec 08 §Demo): drive rehearsal ×2, stopwatch <4 min,
      assign who speaks which beat.
