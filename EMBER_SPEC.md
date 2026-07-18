# Ember — Technical Spec & Implementation Plan (v2, API-only)
### Carbon-aware AI inference orchestrator across enterprise model tiers
*Hack the 6ix · 36-hour build · primary target: Deloitte "Green AI, and AI for Green"*

> v2 supersedes v1 and the Verdant handoff doc. **Architecture change:** no local
> models, no Ollama, no hardware power metering. Ember routes across hosted
> enterprise/API model tiers; energy is **estimated via a transparent, documented
> methodology** and every number is labeled as such. Cost savings are now 100% real
> (actual API price deltas). Naming note: "Ember" collides with ember-climate.org
> (energy think tank) and Ember.js — fine for a hackathon.

---

## 0. What this is, in one paragraph

Standard AI apps send every request to a frontier model. Ember is a routing layer
that, per request, (a) **right-sizes**: picks the cheapest/smallest hosted model that
passes a quality gate, escalating only when needed, and (b) **places carbon-aware**:
given live grid carbon intensity per region (Electricity Maps), selects the greenest
viable datacenter region — simulated in the demo, a real region dropdown on
Bedrock/Azure in production. Impact chain: `tokens × per-token energy figures
(published/derived, input vs output separately) × datacenter PUE = kWh`, then
`kWh × live grid intensity (gCO₂/kWh, grid-operator data via Electricity Maps) =
gCO₂`. An A/B harness proves Ember cuts estimated CO₂ and **real dollars** versus
send-everything-to-frontier, at equal answer quality. We do NOT train anything;
training/embodied emissions are declared out of scope per the SCI standard.

**Quality parity is the hard constraint; carbon/cost is the objective.** Formally
(the GAR paper's framing): minimize gCO₂ *subject to* accuracy ≥ baseline. Ember
never trades answer quality for greenness — a query that needs the frontier model
gets the frontier model. Savings come only from not wasting frontier compute on
queries a smaller model provably answers just as well. When in doubt, escalate.

**Honest pitch line:** "Cost savings are exact. Carbon numbers are estimates — but
they're *transparent* estimates, every assumption stated, which is more than the
industry gives you today."

---

## 1. Locked decision sheet (v2)

| # | Decision | Ruling |
|---|---|---|
| D1 | Models | Hosted API tiers only, zero downloads. Config-driven ladder per provider. Preferred: a ladder with **known parameter counts** (open-weight models hosted on Groq/Together — free/cheap keys, public sizes → most defensible energy estimates). Also supported: Anthropic (haiku→sonnet→opus) / OpenAI (4o-mini→4o) ladders, with parameter-count assumptions stated. Pick by what keys/credits we get (O1). |
| D2 | Energy | Estimation engine: `E_kWh = (tok_in × Wh_in(model) + tok_out × Wh_out(model)) × PUE / 1000`. Factors from EcoLogits methodology + provider disclosures (Google, Mistral lifecycle report, etc.), stored in `data/energy_factors.json` with source + date per row. PUE = provider-stated or 1.2 (assumption, stated). Everything labeled **estimated** — no exceptions. |
| D3 | Region attribution | Assumed default datacenter region per provider (e.g., US-East for OpenAI/Azure), stated in methodology. Arm B's simulated pick recorded separately (D5). |
| D4 | Overhead accounting | Ember's total includes classifier tokens + judge tokens + ALL escalation attempts (energy AND cost). Baseline pays only its own calls. Non-negotiable honesty rule. |
| D5 | Placement | **Simulated**: real Electricity Maps live data, real selection logic, label "projected — provider region not controllable via public API; real region selection exists on Bedrock/Azure" (the path-to-production slide). |
| D6 | Deferral/forecast scheduling | Cut. Forecast chart in methodology view only if trivial. |
| D7 | Cost | Real per-token API prices per model (config price table). Headline cost saving is exact. Training emissions = embodied, out of scope per SCI (M=0), stated. |
| D8 | Quality gate | Judge-everything: every non-top-tier answer scored by judge before acceptance. Benchmark additionally checks ground truth where labels exist. **Parity is the constraint, not a preference — ambiguous verdicts escalate.** The headline claim is always "accuracy within X% of frontier baseline," measured, shown next to the savings. |
| D9 | Judge | One tier up from the answering model. Top-tier answers un-judged. Judge tokens count (D4). |
| D10 | Escalation | One tier at a time, max 2 hops, hard stop at top. All escalations logged + shown ("escalation rate" is a feature, healthy band ~10–30%). |
| D11 | Latency | APIs are fast; demo can run live. Classifier <300ms (heuristics + optional cheapest-tier call). Record p50/p95 anyway — "and it's faster" is a free demo line. |
| D12 | Baseline arm | Everything → top tier of the ladder, default region. Extrapolation slide scales to fleet volume (1M queries/day → t/yr), labeled estimate. |
| D13 | Workload | ~150 queries: GSM8K subset (ground truth), hand-written trivial QA/formatting, small code tasks w/ unit-test oracles, light reasoning. Provenance stated per category. |
| D14 | Benchmark execution | Interleaved (A,B,A,B…), K=3, resumable, rate-limit-aware (bounded concurrency ~4, exponential backoff on 429). Runs in <1h — no overnight dependency, but full run is stored and demo can replay it offline. |
| D15 | Stack | Python 3.11 + FastAPI + SQLite (SQLAlchemy); React + Vite + Recharts; 1s polling; localhost. |
| D16 | Live counters | Smoothly animated between real per-query data points; methodology says so. |
| D17 | View cut-line | Must-have: race view, result card, methodology, ESG/SCI report. Stretch: leaderboard, badge, SDK (`ember.route()`). |
| D18 | Persistence | All runs persisted; dashboard fully functional offline from stored results; live mode degrades to replay with visible "replay" tag — never fake liveness. |

**OPEN items:**
- O1: Which API keys/credits do we have? (Check sponsor perks — hackathons often hand out OpenAI/Anthropic/Groq credits. Groq free tier alone is enough.) → fixes the ladder.
- O2: Team size + who knows Python/React → assign the three tracks.
- O3: Electricity Maps token confirmed working.
- O4: The 4-line token-emissions considerations list (pasted text #3) — fold into methodology.

---

## 2. Concepts explainer (for the team + the judges)

- **Training vs inference.** Training already happened (provider's datacenter, months,
  one-time). Inference = running your prompt through the trained weights — the only
  thing we count. Training carbon = "embodied," declared out of scope per SCI.
- **Why energy is an estimate now.** The compute happens in a provider datacenter with
  no per-request energy API. Estimation basis: model size (known for open-weight
  models like Llama; *assumed* for closed ones — stated), tokens processed, GPU
  efficiency figures, datacenter PUE. This is the EcoLogits approach; it's the best
  available and we say exactly that.
- **Prefill vs decode — why input/output tokens have different factors.** Input
  (prompt) tokens are processed in one parallel pass — cheap per token. Output tokens
  are generated one at a time, each requiring a full forward pass — roughly an order
  of magnitude costlier per token. Our factor table keeps them separate.
- **PUE (Power Usage Effectiveness).** Datacenter total power ÷ IT-equipment power;
  covers cooling/overhead. Hyperscalers ~1.1–1.2; world average ~1.5. We multiply
  estimated chip energy by PUE and state which value we assumed.
- **Grid carbon intensity — how Electricity Maps connects.** Energy ≠ carbon: the same
  kWh is ~30 gCO₂ in Quebec (hydro), ~650 in Poland (coal), and varies hour by hour.
  Grid operators (IESO, CAISO, ENTSO-E…) publish live generation mix; Electricity Maps
  aggregates those official feeds and converts to gCO₂eq/kWh via IPCC per-source
  factors (open-source methodology). It enters Ember twice: **attribution** (which
  region's intensity multiplies our kWh) and **optimization** (the router picks the
  lowest-intensity viable region *right now* — the live feed IS the decision input).
  Average vs marginal: we use average intensity (marginal needs WattTime PRO); stated.
- **SCI (Green Software Foundation).** `SCI = (E × I + M) / R`. Ours: E estimated
  kWh, I from Electricity Maps, M = 0 (declared), R = one query.

---

## 3. Architecture

```
 client / demo ──► FastAPI ──┬─ /route            one query through Ember
                             ├─ /benchmark/run    A/B harness (async job)
                             ├─ /runs/{id}        poll: progress + per-query events
                             ├─ /report/{id}      SCI/ESG report JSON
                             └─ /meta/methodology assumptions, sources, factor table

 ROUTER: classifier (heuristics + optional cheapest-tier call) → tier
         → selector (greenest candidate region, simulated, labeled)
         → provider API call (captures usage.tokens, latency)
         → quality gate (judge = tier+1) → accept | escalate (≤2 hops)

 MEASUREMENT: energy.py estimator (factor table × tokens × PUE) → kWh (estimated)
              carbon.py ElectricityMaps client (60s cache → disk snapshot →
              static labeled fallback factors)
              calculator.py: gCO2 = kWh × I(zone, t); cost from real price table

 DB (SQLite): runs, query_results (arm, model, tok_in/out, kwh_est, zone_assumed,
              zone_simulated, intensity, gco2, cost_usd, latency, escalations,
              quality_score, labels), carbon_snapshots, reports.

 DASHBOARD (React+Vite, 1s polling): Race view (two animated CO₂+$ counters),
              Result card, Methodology (factor table + sources rendered),
              ESG/SCI report. Stretch: leaderboard.
```

```
 ember/
   backend/
     app.py                    config.py            .env.example
     router/    classifier.py  selector.py  quality_gate.py
     providers/ base.py  groq.py  openai.py  anthropic.py   # thin, uniform interface
     measurement/ energy.py  carbon.py  calculator.py
     benchmark/ workloads.py  harness.py  scoring.py  report.py
     db/        models.py  store.py
   dashboard/                  # React + Vite
   data/       energy_factors.json  price_table.json  fallback_intensity.json
               workloads/  snapshots/
```

---

## 4. Measurement methodology (the 30%-weight section)

1. **Token truth:** token counts come from the provider's `usage` field (exact), never
   from our own tokenizer guess.
2. **Energy:** `E = (tok_in × f_in + tok_out × f_out) × PUE`. Factor table
   `energy_factors.json`: per model → `{wh_per_1k_in, wh_per_1k_out, params_known:
   bool, source, source_date, assumptions}`. Populated at build time from EcoLogits +
   provider disclosures. Rendered verbatim in the methodology view — judges can read
   every row.
3. **Carbon:** `gCO2 = E_kWh × I(zone, t)`. Arm A: assumed provider region. Arm B:
   simulated greenest pick, labeled. Local wall-clock intensity snapshot stored with
   every result for auditability.
4. **Cost:** exact, from the provider price sheet — the number that needs zero caveats.
5. **Honesty guardrails:** identical inputs both arms; classifier/judge/escalation
   tokens all counted in Ember's totals; failed queries included; escalation rate
   displayed; every displayed number carries `estimated | live-grid | fallback` tags;
   scope statement (operational inference only; average not marginal intensity;
   assumed regions; assumed params for closed models).

---

## 5. Edge cases & failure modes

**Provider APIs**
- 429 rate limits → bounded concurrency (~4) + exponential backoff + resumable
  harness (per-query commit; resumes from last completed index).
- Quota/credit exhaustion mid-benchmark → harness prints spend estimate up front
  (~150 queries × K=3 × 2 arms + judges ≈ small $, verify against credits); resumable
  after topping up.
- Provider outage / venue Wi-Fi dead → demo replays stored full run (D18) with
  visible "replay" tag; result card, methodology, report all work offline.
- Missing `usage` field / streaming quirks → non-streaming calls in benchmark mode;
  assert usage present, else mark result invalid (never guess tokens silently).
- Timeout (120s) → marked failed, cost/energy of the attempt still counted.

**Energy estimation**
- Closed model with unknown params/architecture (MoE etc.) → factor row carries
  `params_known: false` + stated assumption; methodology view surfaces it. Prefer a
  known-params ladder (D1) to minimize these rows.
- Conflicting published figures → record chosen value + alternatives in the source
  notes; sensitivity note in methodology ("±2× on energy would still leave X%
  savings" — savings are ratio-driven, dominated by model-size gap, so the *relative*
  story is robust to factor error; say this out loud, it's the best defense).

**Electricity Maps**
- API down / token dead / rate-limited → 60s in-memory cache → last-good disk
  snapshot → static per-zone fallback factors (sourced, dated, labeled `fallback`).
  Pre-fetch snapshots before judging; demo never depends on live network.
- Zone returns null → drop from candidate set for that cycle.

**Router / quality gate**
- Judge returns unparseable score → one strict-format retry, then treat as fail →
  escalate (safe direction).
- Everything/nothing escalates → tune `QUALITY_FLOOR` on a 20-query dry run before
  the full benchmark; escalation rate displayed (10–30% healthy band).
- Classifier misroutes → safe by design: under-routing caught by gate (costs tokens,
  not quality); over-routing costs savings only.
- Top-tier answer wrong → shows up in both arms' accuracy; claim is always "accuracy
  within X% of baseline," never "always right."
- Judge disagrees with ground truth (benchmark) → ground truth wins for accuracy
  scoring; disagreement rate logged (nice methodology footnote on judge reliability).

**Benchmark / demo**
- Savings look small because ladder tiers are too close (e.g., 4o-mini vs 4o pricing
  gap ≠ energy gap) → prefer a ladder with a wide size spread (1B/8B/70B-class);
  verify the demo delta on the dry run, not on stage.
- Two counters visually boring → real fix is workload mix (more trivial queries →
  more right-sizing wins); never inflate factors.

---

## 6. Build plan — 36 hours, 3 tracks

**A = measurement/backend · B = router/benchmark · C = dashboard.** No downloads, no
overnight compute — the critical path is just build + one <1h benchmark run.

| Hours | Track A | Track B | Track C |
|---|---|---|---|
| 0–2 | Scaffold, `.env`, **verify API keys + EM token**, draft `energy_factors.json` + `price_table.json`. **Gate: print "this call used ~N tokens → ~X Wh → ~Y gCO₂ (estimated)" for one real API call.** | Provider wrappers (uniform interface), classifier heuristics | Vite scaffold, layout, race view on mock JSON |
| 2–8 | `energy.py`, `carbon.py` (cache→snapshot→fallback), `calculator.py`, DB models | Quality gate + judge + escalation; `route()` end-to-end | Race view + result card polished against mock contract |
| 8–14 | FastAPI endpoints, `/runs` polling contract, labels everywhere | Workloads (150 queries) + scoring oracles | Wire real endpoints; methodology view (renders factor table + sources) |
| 14–20 | Support, spend estimator, snapshot pre-fetch | Harness: interleaved, K=3, resumable, backoff; **20-query dry run → tune QUALITY_FLOOR** | ESG/SCI report render |
| 20–26 | **Full benchmark run (<1h) + verify numbers**; extrapolation math | Fix escalation weirdness; re-run if needed (cheap now) | Charts from real data; replay mode |
| 26–32 | Freeze data; offline-mode test (Wi-Fi off, everything must render) | Stretch only if solid: leaderboard / `ember.route()` SDK | Polish, demo mode |
| 32–36 | **Rehearse demo twice, airplane-mode test, sleep** | ← | ← |

---

## 7. Demo script (laptop judging, ~3 min)

1. "Every AI product sends every query to a frontier model — a truck to buy milk.
   And nobody can tell you what any of it emits." Show workload: 150 queries,
   trivial→hard.
2. **Run comparison** — live (APIs are fast), stored full run behind it. Two counters
   diverge: gCO₂ *and dollars*.
3. Result card: **"−X% CO₂ (est.) · accuracy within Y% · −Z% cost (exact) · faster
   p50."** "Same answers. The dollars are exact. The carbon is an estimate — and
   here's every assumption."
4. Methodology click: factor table with sources on screen, token→Wh→gCO₂ chain,
   Electricity Maps = live grid-operator data, scope statement. "Transparent beats
   silent."
5. ESG report: SCI per query + reduction — "what Deloitte's clients need to file."
6. Path to production: "On Bedrock/Azure, region choice is a real dropdown — the
   placement half stops being simulated the day you deploy."
7. Close: extrapolation to 1M queries/day → tonnes/yr (labeled), "adopted for the
   cost savings, green by construction."

---

## 8. `.env.example`

```
# Provider keys (fill what we have — O1)
GROQ_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
ELECTRICITYMAPS_TOKEN=

# Model ladder (uniform: provider:model, cheapest→frontier)
MODEL_TRIVIAL=groq:llama-3.1-8b-instant
MODEL_MODERATE=groq:llama-3.3-70b-versatile
MODEL_HARD=openai:gpt-4o            # or anthropic:claude-sonnet-5
JUDGE_STRATEGY=tier_plus_one

BASELINE_ZONE=US-MIDA-PJM           # assumed default provider region (stated)
CARBON_ZONES=SE,FR,US-CAL-CISO,CA-ON,PL
QUALITY_FLOOR=0.85
EM_CACHE_S=60
PUE_DEFAULT=1.2
MAX_CONCURRENCY=4
```
