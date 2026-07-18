# Ember 🔥

**Carbon-aware AI inference orchestrator.** Every query goes to the smallest model
that passes a quality gate — frontier-level answers, without frontier-level waste —
and every call is scored with a transparent carbon methodology and exact cost.

Built in 36 hours at Hack the 6ix 2026.

**New here?** Read in this order:
1. [`EXPLAINER.md`](./EXPLAINER.md) — the whole project in plain English: what it
   does, every feature, what it uses, how it connects. No jargon.
2. [`OVERVIEW.md`](./OVERVIEW.md) — the technical map: diagrams, objectives,
   4-person delegation.
3. [`specs/`](./specs/README.md) — one detailed spec per domain + your personal
   task list in `specs/tasks/`.

Tests: `uv run pytest` — fast, offline, no keys needed; every test's docstring
says what it protects and why.

## The impact chain

```
tokens (provider usage field, exact)
  × per-token energy factors (sourced, input/output separate)
  × datacenter PUE                          =  kWh   (estimated, labeled)
  × live grid carbon intensity              =  gCO₂  (Electricity Maps → grid operators)
```

Quality parity is the hard constraint; carbon and cost are the objective.
A judge model verifies every small-model answer and escalates on any doubt —
savings come from not wasting frontier compute on trivial queries, never from
degraded answers.

## Quickstart

```bash
cp .env.example .env        # add GROQ_API_KEY (free: console.groq.com/keys)
uv sync
uv run python -m backend.smoke "What is the capital of France?"
```

## Layout

```
backend/
  providers/     uniform API-provider interface (Groq, OpenAI-compatible)
  measurement/   energy estimator · Electricity Maps client · impact calculator
  router/        difficulty classifier · carbon-aware selector · quality gate
  benchmark/     A/B harness: baseline (all-frontier) vs Ember, same inputs
  db/            SQLite persistence
dashboard/       React + Vite live comparison dashboard
data/            energy factors, price table, fallback intensities (all sourced)
```
