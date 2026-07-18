# 00 — Overview & Locked Decisions

*Hack the 6ix · 36-hour build · primary target: Deloitte "Green AI, and AI for Green"*

## Concept

Standard AI apps send every request to a frontier model. Ember is a routing layer
that, per request, (a) **right-sizes**: picks the cheapest/smallest hosted model that
passes a quality gate, escalating only when needed, and (b) **places carbon-aware**:
given live grid carbon intensity per region (Electricity Maps), selects the greenest
viable datacenter region — simulated in the demo, a real region dropdown on
Bedrock/Azure in production. An A/B harness proves Ember cuts estimated CO₂ and
**real dollars** versus send-everything-to-frontier, at equal answer quality.

**Quality parity is the hard constraint; carbon/cost is the objective.** Formally
(GAR framing): minimize gCO₂ *subject to* accuracy ≥ frontier baseline. The frontier
tier and the baseline arm are both **the latest Claude Opus** — Ember's claim is
literal parity with the most capable model, never eco-friendliness at quality's
expense. Savings come only from not wasting frontier compute on queries a smaller
model provably answers just as well. When in doubt, escalate.

**The impact chain:**
```
tokens (provider usage field, exact)
  × per-token energy factors (sourced, input/output separate)
  × datacenter PUE                              =  kWh   (estimated, labeled)
  × live grid carbon intensity (gCO₂/kWh)       =  gCO₂  (Electricity Maps → grid operators)
```

**Honest pitch line:** "Cost savings are exact. Carbon numbers are estimates — but
they're *transparent* estimates, every assumption stated, which is more than the
industry gives you today."

**The vendor story:** Meta's open models (via Groq) do the cheap work, Anthropic's
Opus is the frontier guarantee, Google's Gemini is the independent referee.

## Prize strategy (Deloitte rubric)

| Criterion | Weight | How Ember maxes it |
|---|---|---|
| Environmental Impact | 30% | Transparent estimation chain, every assumption stated and rendered in a methodology view; live grid data; SCI-framed report; fleet extrapolation |
| Innovation & Creativity | 25% | Research-proven routing (GAR ~74% reduction) packaged as the first adoptable product; independent-family judge design |
| Technical Feasibility | 25% | Real public APIs end to end; the A/B harness is fully buildable and demoable |
| Clarity & Presentation | 20% | Two live CO₂+$ counters diverging on one screen; ESG report artifact |

Stretch prizes (only after MVP): dev-tool SDK (`ember.route()`), leaderboard/badge.

## Locked decision sheet

| # | Decision | Ruling |
|---|---|---|
| D1 | Models | Hosted API tiers only, zero downloads. Ladder: Groq open-weight lower tiers (known params) → **latest Opus frontier tier**. Config-driven; see spec 02. |
| D2 | Energy | Estimated: `E_kWh = (tok_in × f_in + tok_out × f_out) × PUE / 1000`, sourced factor table. Everything labeled **estimated**, no exceptions. See spec 03. |
| D3 | Region attribution | Assumed default datacenter region per provider, stated in methodology. |
| D4 | Overhead accounting | Ember's totals include classifier + judge + ALL escalation attempts (energy and cost). Baseline pays only its own calls. Non-negotiable. |
| D5 | Placement | Simulated: real Electricity Maps data, real selection logic, labeled "projected — real region selection exists on Bedrock/Azure." |
| D6 | Deferral/forecast scheduling | Cut from implementation. |
| D7 | Cost | Real per-token API prices; headline cost saving is exact. Training emissions = embodied, out of scope per SCI (M=0), stated. |
| D8 | Quality gate | Judge-everything for non-frontier answers. **Parity is the constraint, not a preference — ambiguous verdicts escalate.** Claim is "accuracy within X% of all-Opus baseline," measured. |
| D9 | Judge | Independent family: Gemini Flash scores Llama/mid-tier answers (no self-grading bias). Fallback: judge = one tier up. Judge overhead counts (D4). |
| D10 | Escalation | One tier at a time, max 2 hops, hard stop at Opus. All escalations logged + shown; healthy band ~10–30%. |
| D11 | Latency | No hard SLO; record p50/p95 ("and it's faster" is a free demo line). Classifier <300 ms. |
| D12 | Baseline arm | Everything → latest Opus, default region. Extrapolation to fleet volume labeled estimate. |
| D13 | Workload | ~150 queries: GSM8K subset, hand-written trivial QA/formatting, code tasks with unit-test oracles, light reasoning. Provenance stated. |
| D14 | Benchmark execution | Interleaved A,B,A,B; K=3; resumable; bounded concurrency ~4 with backoff. Full run stored; demo can replay offline. |
| D15 | Stack | Python 3.11 + FastAPI + SQLite (SQLAlchemy); React + Vite + Recharts; 1 s polling; localhost. |
| D16 | Live counters | Smoothly animated between real per-query data points; methodology says so. |
| D17 | View cut-line | Must-have: race view, result card, methodology, ESG/SCI report. Stretch: leaderboard, badge, SDK. |
| D18 | Persistence | All runs persisted; dashboard fully functional offline; live mode degrades to replay with a visible tag — never fake liveness. |

## Open items

- **O1 — API keys:** `GEMINI_API_KEY` (hackathon sponsor), `GROQ_API_KEY` (free),
  `ELECTRICITYMAPS_TOKEN` (free), `ANTHROPIC_API_KEY` (~$25–50 credits; check
  sponsor perks). Optional: `OPENAI_API_KEY`.
- **O2 — Team split:** who owns which spec/track.
- **O3 — EM token** confirmed working end to end.
- **O4 —** fold the token-emissions considerations list into spec 03 when received.

## Success criteria

1. `python -m backend.benchmark.harness` prints "Ember cut CO₂ by X% at Y% accuracy
   delta vs all-Opus, Z% cost saving" from one command.
2. The dashboard demo runs end to end with Wi-Fi off (replay mode).
3. Every number on screen carries a provenance label (`estimated | live | cached |
   snapshot | fallback | exact`).
4. Judges can read every energy assumption in the methodology view.
