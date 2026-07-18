# 06 — Storage & Event Stream (`backend/db/`)

CLI pivot note: the former FastAPI layer is gone — the CLI and TUI call the Python
core in-process. What remains here is the persistence contract everything shares:
SQLite is the single source of truth, and the **event stream read from it** is what
`ember race` animates and the harness resumes from.

## Database (SQLite via SQLAlchemy, `data/ember.sqlite`)

```
runs           id PK · started_at · finished_at · status (running|done|failed) ·
               k · workload · config_json (ladder/floor/zones snapshot — reproducibility)
query_results  id PK · run_id FK · task_id · arm (a|b) · k_index · seq (event cursor) ·
               role (answer|classifier|judge) · model_key · tier ·
               tokens_in · tokens_out · wh · gco2 · cost_usd · latency_ms ·
               zone · gco2_per_kwh · intensity_label · energy_label ·
               score · correct · answer (text, answer rows only — spec-09 blind
               pairwise judging needs both arms' texts) · escalated_from · error
carbon_snapshots  zone · gco2_per_kwh · label · fetched_at
reports        run_id FK · report_json · created_at
```

Design rules:
- **One row per call** — answer, classifier, judge — so D4 overhead accounting is
  auditable straight from SQL (`SELECT role, SUM(gco2) ... GROUP BY role`).
- `seq` is a monotonically increasing per-run cursor: the TUI's incremental read
  key and the guarantee that replays reproduce the original order.
- `config_json` snapshot on every run: any report is reproducible/explainable later.
- Writers commit per call, never batch — a crash loses at most one call (resume
  support, spec 05).

## Store API (`backend/db/store.py`) — ✅ built (implemented by P3 to unblock the
harness; the P1-M2/M3 stubs were unclaimed — P1 pull before continuing)

```python
init_db()
create_run(run_id, k, workload)             # opens run + config_json snapshot
finish_run(run_id, status="done")
record_call(run_id, task_id, arm, k_index, role, impact, **kw) -> int   # returns seq
get_run_events(run_id, after_seq=0) -> list[dict]   # ordered, the race-view feed
run_totals(run_id) -> dict                  # per-arm sums (ALL roles, D4) + escalations
completed_tuples(run_id) -> set             # (task_id, arm, k_index) of clean ANSWER rows
get_answer_rows(run_id) -> list[dict]       # evaluation's raw material (spec 09)
get_run_config(run_id) -> dict
list_runs() -> list[dict]                   # for `ember race` / `ember report` pickers
save_report(run_id, report) / load_report(run_id)
```

Resume semantics: only clean `answer` rows count as completed — a crash between an
overhead call and its answer re-runs the whole (task, arm, k) so pairs stay whole.

Event dict shape (what `get_run_events` returns — the contract `ember race`
renders; keep stable):
```json
{"seq": 74, "task_id": "gsm8k-017", "arm": "b", "role": "answer",
 "tier": "moderate", "gco2": 0.011, "cost_usd": 0.0011, "wh": 0.03,
 "correct": true, "escalated_from": "trivial",
 "energy_label": "estimated", "intensity_label": "live"}
```

## Concurrency note

Harness workers (bounded, ~4) write from threads; SQLite handles this with the
default serialized mode + per-call commits. Keep transactions tiny; never hold a
session across an API call.

## Acceptance criteria

- Kill the harness mid-run; `completed_tuples` lets it resume with zero duplicate
  (task, arm, k) rows.
- `get_run_events(run_id, after_seq=N)` returns exactly the events after N, ordered.
- Restart the process: `list_runs`, events, and reports all still served —
  `ember race` replay and `ember report` work with Wi-Fi off (D18/KR4.1).
