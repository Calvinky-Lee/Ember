# 01 — Architecture

## System topology (CLI-first — pivot decision, D15)

```
 terminal ──► ember CLI ──┬─ route "…"      one query through Ember + impact receipt
                          ├─ benchmark      A/B harness (spend confirm up front)
                          ├─ race           live/replay TUI: diverging CO₂+$ counters
                          ├─ report --html  self-contained ESG/SCI artifact
                          ├─ methodology    audit trail: factors, sources, scope
                          └─ doctor         keys / data / EM health check

 ROUTER: classifier (heuristics + optional cheapest-tier call) → tier
         → selector (greenest candidate region, simulated, labeled)
         → provider API call (usage.tokens, latency)
         → quality gate (Gemini judge) → accept | escalate (≤2 hops, stop at Opus)

 MEASUREMENT: energy estimator (factor table × tokens × PUE) → kWh (estimated)
              ElectricityMaps client (live → 60s cache → disk snapshot → fallback)
              calculator: gCO2 = kWh × I(zone, t); cost from real price table

 DB (SQLite): runs, query_results (event stream via seq cursor), snapshots, reports
              — single source of truth; race view and reports read ONLY from here

 (stretch) MCP server: route_query / carbon_report tools for Claude Desktop/Code
```

## Repository layout

```
ember/
  specs/                    # these documents — one per domain
  backend/
    cli.py                  # `ember` entry point (spec 07)
    tui/                    # spec 07 — Textual race view (P4)
    report_html.py          # spec 07 — self-contained HTML report (P4)
    config.py               # env, ladder, zones, thresholds — single source of truth
    smoke.py                # Phase-0 gate: one real call through the impact chain
    providers/              # spec 02 — base.py, openai_compat.py, anthropic.py, registry.py
    measurement/            # spec 03 — energy.py, carbon.py, calculator.py
    router/                 # spec 04 — classifier.py, selector.py, quality_gate.py, route.py
    benchmark/              # spec 05 — workloads.py, harness.py, scoring.py, report.py
    db/                     # spec 06 — models.py, store.py
  tests/                    # offline suite — every test documents what it protects
  data/
    energy_factors.json     # sourced Wh/1k-token rows per model (spec 03)
    price_table.json        # exact USD/1M-token rows per model (spec 03)
    fallback_intensity.json # static labeled gCO2/kWh per zone (spec 03)
    workloads/              # benchmark query sets (spec 05)
    snapshots/              # last-good EM responses (gitignored)
  pyproject.toml            # uv-managed; `uv sync && uv run ember doctor`
  .env.example
```

## Request lifecycle (`ember route`)

1. `classifier.classify(query)` → tier ∈ {trivial, moderate, hard} (<300 ms).
2. `selector.pick_zone()` → greenest candidate zone (simulated placement, labeled).
3. `registry.chat(ladder[tier], messages)` → answer + exact token counts.
4. If tier ≠ hard: `quality_gate.verify(query, answer)` via Gemini judge.
   Fail/ambiguous → escalate one tier, re-run 3–4 (max 2 hops; Opus accepted unjudged).
5. `calculator.measure(...)` for the answer call **and every overhead call** (D4).
6. Persist a `query_results` row per call; respond with answer + impact record.

## Config (`backend/config.py`)

All tunables come from `.env` via `config.py` — no constants buried in modules.
Key names: `MODEL_TRIVIAL/MODERATE/HARD`, `JUDGE_MODEL`, `BASELINE_ZONE`,
`CARBON_ZONES`, `QUALITY_FLOOR`, `EM_CACHE_S`, `PUE_DEFAULT`, `MAX_CONCURRENCY`.
See `.env.example` for defaults and per-key commentary.

## Cross-cutting rules

- **Serial truth, labeled provenance:** every number that reaches the UI carries a
  label (`estimated | exact | live | cached | snapshot | fallback | replay`).
- **Never guess silently:** missing usage field → invalid result; unknown model key →
  hard error pointing at the data file to fix.
- **Offline-first demo:** any view must render from persisted data with Wi-Fi off.
- **Spec-code lockstep:** changing a contract means updating the owning spec in the
  same commit.
