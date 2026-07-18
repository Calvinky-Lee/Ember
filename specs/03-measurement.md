# 03 — Measurement (`backend/measurement/`) — ✅ built

The impact chain: tokens → estimated kWh → gCO₂ at a zone's live intensity, plus
exact cost. This spec is the basis of the methodology view (Deloitte's 30% criterion).

## The formulas

```
E_kWh  = (tok_in × wh_per_1k_in + tok_out × wh_per_1k_out) / 1000 × PUE / 1000
gCO2   = E_kWh × I(zone, t)          # I from Electricity Maps, gCO2eq/kWh
cost   = tok_in/1e6 × usd_per_1m_in + tok_out/1e6 × usd_per_1m_out   # EXACT
SCI    = (E × I + M) / R             # M = 0 (embodied, declared out of scope), R = one query
```

Input vs output factors differ because prefill (prompt) tokens process in one
parallel pass while decode (output) tokens each require a full forward pass —
roughly an order of magnitude costlier per token.

## Files & contracts

### `energy.py`
`estimate_wh(model_key, tokens_in, tokens_out) → {wh, kwh, chip_wh, pue, label:
"estimated", params_known, factor_source}`. Unknown model key → `UnknownModelError`
pointing at the data file — never a silent default.

### `carbon.py`
`get_intensity(zone) → {zone, gco2_per_kwh, label, fetched_at}` with the
**degradation ladder**: live API → 60 s in-memory cache → last-good disk snapshot
(`data/snapshots/intensity.json`, written on every live success) → static
`data/fallback_intensity.json`. Label reflects the rung: `live | cached | snapshot |
fallback`. `greenest_zone(zones?) → intensity` = min over candidates; zones that
error are dropped for that cycle.

Electricity Maps: `GET /v3/carbon-intensity/latest?zone={Z}`, `auth-token` header.
No token → skips straight down the ladder (the system runs keyless, labeled).

### `calculator.py`
`measure(model_key, tokens_in, tokens_out, zone) → dict` — the full per-call impact
record: energy + label, intensity + label, gCO₂, exact cost. `cost_usd(...)` exposed
separately for spend estimation.

## Data files (all rows carry source + date)

- **`energy_factors.json`** — per `provider:model`: `wh_per_1k_in/out`, `params_b`,
  `params_known`, `architecture`, `source`, `assumptions`. Open-weight rows are
  derived from J/output-token anchors (1 J/token = 0.278 Wh/1k); closed-model rows
  are flagged `params_known: false` with a stated frontier-class assumption. The
  methodology view renders this file verbatim.
  **TODO(build hours 0–2): verify v0 values against EcoLogits published figures.**
- **`price_table.json`** — exact USD/1M tokens from provider price sheets.
  **TODO: verify against groq.com/pricing + anthropic + google price pages.**
- **`fallback_intensity.json`** — approximate yearly-average gCO₂/kWh per zone,
  used only at the bottom of the ladder, always labeled.

## Methodology view content (rendered by dashboard, spec 07)

1. The chain diagram with formulas above.
2. The factor table verbatim, `params_known` flags surfaced.
3. Scope statement: operational inference only; training/embodied excluded (SCI M=0);
   average not marginal intensity; assumed provider regions; simulated placement.
4. Sensitivity note: savings are ratio-driven (model-size gap), so ±2× factor error
   barely moves the percentage — the relative story is robust.
5. Grid data provenance: grid operators (IESO, CAISO, ENTSO-E…) → Electricity Maps
   (open-source methodology, IPCC per-source emission factors).

## Edge cases

- EM API down / token dead / rate-limited → degradation ladder, labeled; pre-fetch
  snapshots before judging so the demo never needs live network.
- Zone returns null intensity → dropped from candidates for that cycle.
- Unknown model key in either table → loud error naming the file to fix.
- Conflicting published energy figures → record chosen value + alternatives in the
  row's source notes.

## Acceptance criteria (Phase-0 gate — ✅ passing)

`uv run python -m backend.smoke "..."` prints the full chain for one real call:
tokens (exact) → Wh (estimated, PUE stated) → zone @ intensity [label] → gCO₂ →
cost (exact) → latency.
