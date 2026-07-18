# 07 — Dashboard (`dashboard/`)

React + Vite + Recharts. Scanned, not read: the summary must land before the detail.
Build against mock JSON of the spec-06 contracts first; swap to real endpoints after.

## Views (must-have, D17)

### 1. Race view (the demo centerpiece)
- Two big counters — **gCO₂** and **$** — one pair per arm ("All-Opus baseline" vs
  "Ember"), animating smoothly between real `/runs/{id}` events (D16; poll 1 s,
  `?after_seq` cursor).
- Under the counters: progress (pairs completed), live escalation rate chip,
  per-query event ticker (task id · arm · tier badge · gCO₂ · ✓/✗).
- Every number renders its provenance tag: `estimated`, `exact`, `live/fallback`.
- **Replay mode:** if the run is finished (or network is down), the same view
  replays persisted events on a timer with a visible `REPLAY` tag — never fake
  liveness (D18).

### 2. Result card
The headline: **“−X% CO₂ (est.) · accuracy within Y% of all-Opus · −Z% cost (exact)
· faster p50.”** Secondary row: escalation rate, per-arm accuracy, per-query SCI.
One `Extrapolate` toggle → fleet scale (1M queries/day → t CO₂/yr, labeled estimate).

### 3. Methodology view
Renders `/meta/methodology` verbatim: the impact-chain diagram, the energy factor
table with `params_known` flags and sources, scope statement, sensitivity note,
grid-data provenance chain (grid operators → Electricity Maps → IPCC factors).
This page is the Deloitte 30% answer — it must feel like an audit document.

### 4. ESG / SCI report
Rendered `/report/{id}`: SCI per functional unit, reduction vs baseline, labels,
methodology summary. Print-friendly CSS (`@media print`) — "hand this to compliance."

Stretch (only after 1–4 are solid): leaderboard + shareable badge.

## Component sketch

```
App ── nav (Race | Result | Methodology | Report) · run picker (GET /runs)
 ├─ RaceView      usePoll(runId) → CounterPair, ProgressBar, EscalationChip, EventTicker
 ├─ ResultCard    useReport(runId) → HeadlineStats, ArmTable, ExtrapolateToggle
 ├─ Methodology   useMeta() → ChainDiagram, FactorTable, ScopeList
 └─ Report        useReport(runId) → SciBlock, ReductionBlock, PrintButton
```

`usePoll`: 1 s interval, cursor param, stops on `status: done`, exposes
`{events, totals, status, stale}` — `stale` (no response >5 s) flips the view to
replay-from-store rather than spinning.

## Design tokens

Ember identity: warm ember accent `#C05621` on warm-grey paper `#FAF9F6`, ink
`#24281F`, moss green `#2E6E52` for good/clean values, red only for failures.
Dark theme equivalents (`#191B17` ground, `#E58A4B` accent). Tabular numerals on
all counters and tables. Arm colors: baseline = neutral grey, Ember = ember accent —
the diverging counters must be tellable apart from the back of a room.

## Mock contract

`dashboard/src/mocks/` carries one canned `/runs/{id}` event stream + one report +
one methodology payload, matching spec 06 exactly. `VITE_USE_MOCKS=1` switches the
hooks; this is also the offline safety net during the demo.

## Acceptance criteria

- Race view animates from mocks with `VITE_USE_MOCKS=1` and from a real running
  benchmark without code changes.
- Wi-Fi off + server restart → all four views still render from persisted data.
- Every displayed number shows its label on hover or inline.
- The result card reads correctly at 2 m distance (demo-table test).
