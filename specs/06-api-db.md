# 06 — API & Database (`backend/app.py`, `backend/db/`)

Thin FastAPI layer + SQLite persistence. The API contract here is what the
dashboard (spec 07) builds against — mock JSON first, real endpoints after.

## Endpoints

| Method & path | Purpose | Response (abridged) |
|---|---|---|
| `POST /route` | one query through Ember | `route()` result (spec 04) |
| `POST /benchmark/run` | start A/B harness async | `{"run_id": ..., "spend_estimate_usd": ...}` |
| `GET /runs/{id}` | 1 s polling for live views | see below |
| `GET /runs` | list persisted runs | `[{id, started_at, status, headline?}]` |
| `GET /report/{id}` | final SCI/ESG report | report dict (spec 05) |
| `GET /meta/methodology` | assumptions + factor table | factor/price/fallback files + scope statement |
| `GET /healthz` | key + data-file status | per-provider key present?, EM reachable?, tables loaded |

### `GET /runs/{id}` — the polling contract
```json
{"run_id": "...", "status": "running|done|failed",
 "progress": {"completed_pairs": 37, "total_pairs": 150, "k": 3},
 "totals": {"a": {"gco2": ..., "cost_usd": ..., "correct": ...},
            "b": {"gco2": ..., "cost_usd": ..., "correct": ..., "escalations": ...}},
 "events": [{"seq": 74, "task_id": "gsm8k-017", "arm": "b", "tier_final": "trivial",
             "gco2": ..., "cost_usd": ..., "correct": true, "escalated": false}],
 "labels": {"energy": "estimated", "intensity_mode": "live|fallback"}}
```
`?after_seq=N` returns only newer events — the race view animates between them (D16).

## Database (SQLite via SQLAlchemy, `data/ember.sqlite`)

```
runs           id PK · started_at · finished_at · status · k · workload ·
               config_json (full ladder/floor/zones snapshot — reproducibility)
query_results  id PK · run_id FK · task_id · arm · k_index · seq ·
               role (answer|classifier|judge) · model_key · tier ·
               tokens_in · tokens_out · wh · gco2 · cost_usd · latency_ms ·
               zone · gco2_per_kwh · intensity_label · energy_label ·
               score · correct · escalated_from · error
carbon_snapshots  zone · gco2_per_kwh · label · fetched_at
reports        run_id FK · report_json · created_at
```

Design notes:
- One `query_results` row **per call**, including classifier/judge overhead
  (`role` column) — D4 auditable straight from SQL.
- `config_json` on runs: a report is always reproducible/explainable later.
- Everything the dashboard needs is derivable from these four tables; no in-memory
  state survives a restart (D18).

## Server rules

- Single process, no auth, localhost only (hackathon scope; stated in README).
- Harness runs in a background task; `/runs/{id}` reads committed rows only —
  polling never blocks on inference.
- CORS open for the Vite dev origin.
- 400 on empty query; 404 on unknown run_id; errors as `{"error": {"message": ...}}`.

## Acceptance criteria

- Start a benchmark, poll `/runs/{id}` from `curl` while it runs — events stream in.
- Kill and restart the server → all runs/reports still served (offline demo works).
- `/healthz` correctly reports which provider keys are missing.
