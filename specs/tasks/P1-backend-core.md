# P1 — Backend Core & Data (specs 03, 06 · KRs 3.1, 3.3, 4.1)

Read first: OVERVIEW.md, specs 00, 01. Your contracts: specs 03 (built — you own
maintenance) and 06 (you build). Everything below is sequenced; each step ends
with a check.

## M1 — Environment + data verification (h0–2)
- [ ] `cp .env.example .env`, fill keys as they arrive. `uv sync`.
- [ ] Run the gate: `uv run python -m backend.smoke "What is 2+2?"` → full chain prints.
- [ ] **Verify factor v0 values** (KR3.3): check `data/energy_factors.json` rows
      against EcoLogits published figures; check `data/price_table.json` against
      groq.com/pricing, anthropic.com/pricing, ai.google.dev/pricing. Update values
      AND `source`/`source_date` fields. Commit: data + spec 03 note in one commit.
- [ ] With `ELECTRICITYMAPS_TOKEN` set: confirm `carbon.get_intensity("CA-ON")`
      returns `label: "live"` and writes `data/snapshots/intensity.json`.

## M2 — Database layer (h2–5) — spec 06 schema
- [ ] `backend/db/models.py`: SQLAlchemy models `Run`, `QueryResult`,
      `CarbonSnapshot`, `Report` exactly per spec 06 (skeleton already in repo —
      fill any TODO columns). One row per call incl. `role` (answer|classifier|judge).
- [ ] `backend/db/store.py`: engine on `data/ember.sqlite`, `init_db()`,
      session helper, `record_call(...)`, `get_run_events(run_id, after_seq)`.
- [ ] Check: `uv run python -c "from backend.db.store import init_db; init_db()"`
      then inspect with `sqlite3 data/ember.sqlite .schema`.

## M3 — FastAPI endpoints (h5–8) — spec 06 contracts, freeze at h8 sync
- [ ] `backend/app.py`: implement `/healthz` (keys present? EM reachable? tables
      loaded?) and `/meta/methodology` (serve the three data files + scope statement).
- [ ] `POST /route` → call P2's `route()` (stub until theirs lands; integrate at h8).
- [ ] `POST /benchmark/run` → background task invoking P3's harness; return
      `run_id` + spend estimate. `GET /runs`, `GET /runs/{id}` (with `after_seq`
      cursor), `GET /report/{id}` per the JSON shapes in spec 06 — **these shapes
      are frozen at h8; P4 builds mocks against them.**
- [ ] CORS for Vite dev origin; error shape `{"error": {"message": ...}}`.
- [ ] Check: `uv run uvicorn backend.app:app` + `curl localhost:8000/healthz`.

## M4 — Labels, spend, resilience (h8–14)
- [ ] Provenance labels present on every numeric field the API returns (KR3.2 dep).
- [ ] Spend estimator util for the harness (price table × workload size × K).
- [ ] Snapshot pre-fetch script: `uv run python -m backend.measurement.prefetch`
      hits all `CARBON_ZONES` once (run before judging).
- [ ] Check: kill server, restart, `GET /runs` still lists prior runs.

## M5 — Freeze support (h20–32)
- [ ] Support P3's full run; verify report numbers land in DB.
- [ ] **Airplane-mode test** (KR4.1) with P4 at h26: Wi-Fi off, restart, all views render.
