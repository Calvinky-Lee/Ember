# 08 — Build Plan & Demo

## 36-hour plan, 3 tracks

**A = measurement/backend (specs 03, 06) · B = router/benchmark (specs 04, 05, 09)
· C = CLI race view + report (spec 07).** No downloads, no overnight compute — critical path is
build + one <1 h benchmark run.

| Hours | Track A | Track B | Track C |
|---|---|---|---|
| 0–2 | ✅ Scaffold, providers, measurement core, data tables, CLI skeleton (`doctor`/`methodology` live). Remaining: **keys in `.env`, run smoke gate live**, verify factor/price v0 values | Provider wrappers ✅; classifier heuristics | Textual race view on synthetic events |
| 2–8 | DB store API: `record_call`, `get_run_events` cursor, resume tuples (spec 06) | Quality gate (Gemini judge) + escalation; `route()` end-to-end | Race view polish: counters, ticker, `--plain` fallback |
| 8–14 | Labels everywhere; store API frozen at h8 | Workloads (150 tasks + oracles) | Wire race view to real `get_run_events`; live-follow + replay banner |
| 14–20 | Spend estimator, snapshot pre-fetch | Harness (interleaved, K=3, resumable, backoff); **20-query dry run → tune QUALITY_FLOOR** | ESG/SCI report render |
| 20–26 | **Full benchmark run (<1 h) + verify numbers**; extrapolation | Evaluation stats (spec 09): paired deltas, CIs, blind judging | Charts from real data; replay mode |
| 26–32 | Freeze data; offline-mode test (Wi-Fi off, everything renders) | Stretch only if solid: leaderboard / `ember.route()` SDK | Polish, demo mode |
| 32–36 | **Rehearse demo twice, airplane-mode test, sleep** | ← | ← |

## Demo script (laptop judging, ~3 min)

1. "Every AI product sends every query to a frontier model — a truck to buy milk.
   And nobody can tell you what any of it emits." Show workload: 150 queries.
2. **Run comparison** — live, stored full run behind it. Two counters diverge:
   gCO₂ *and dollars*.
3. Result card: **"−X% CO₂ (est.) · accuracy within Y% of all-Opus · −Z% cost
   (exact) · faster p50."** "Same answers as the latest Opus — measured, paired,
   blind-judged (spec 09). The dollars are exact."
4. Methodology view: factor table + sources on screen, the token→Wh→gCO₂ chain,
   grid-operator provenance. "Transparent beats silent."
5. ESG report: SCI per query + reduction — "what Deloitte's clients need to file."
6. Vendor story: "Meta's models do the cheap work, Anthropic's Opus is the frontier
   guarantee, Google's Gemini is the referee." Path to production: on Bedrock/Azure
   the region choice is a real dropdown — placement stops being simulated on deploy.
7. Close: extrapolation to 1M queries/day → tonnes/yr (labeled), "adopted for the
   cost savings, green by construction."

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Venue Wi-Fi / provider outage during judging | Everything renders from SQLite; replay mode with visible tag; snapshots pre-fetched (D18) |
| Opus 429/limits during benchmark | Bounded concurrency + backoff + resumable harness (D14) |
| Anthropic credits run out | Up-front spend estimate; fallback frontier `groq:kimi-k2` is one env line |
| Escalation rate looks broken (0% or 60%) | Tuning protocol in spec 05 before the full run |
| Savings delta underwhelming | Workload mix has enough trivial traffic (spec 05 table); never inflate factors |
| Gemini sponsor key gated to other models | `JUDGE_MODEL` is one env line; fallback = tier-plus-one judge |
| Team member blocked | Specs are self-contained per track; synthetic event generator decouples the race view from the backend |
| Broken TTY / terminal weirdness at judging | `ember race --plain` Rich fallback; font size set before judges arrive |

## Definition of done (before rehearsal)

1. One command produces the headline number (spec 00 success criteria).
2. Airplane-mode demo passes.
3. Methodology view renders every assumption.
4. Demo script run twice end to end, timed under 4 minutes.
