"""FastAPI entry — spec 06. /healthz and /meta/methodology are live;
P1 implements the rest per specs/tasks/P1-backend-core.md (M3).
Run: uv run uvicorn backend.app:app --reload"""
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import config

app = FastAPI(title="Ember", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    em_ok = False
    if config.ELECTRICITYMAPS_TOKEN:
        try:
            em_ok = httpx.get(
                "https://api.electricitymap.org/v3/carbon-intensity/latest",
                params={"zone": config.CARBON_ZONES[0]},
                headers={"auth-token": config.ELECTRICITYMAPS_TOKEN},
                timeout=5.0,
            ).status_code == 200
        except httpx.HTTPError:
            pass
    return {
        "keys": {
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "electricitymaps": bool(config.ELECTRICITYMAPS_TOKEN),
        },
        "electricitymaps_reachable": em_ok,
        "ladder": config.MODEL_LADDER,
        "judge": config.JUDGE_MODEL,
        "tables": {
            "energy_factors": len([k for k in config.ENERGY_FACTORS if not k.startswith("_")]),
            "price_table": len([k for k in config.PRICE_TABLE if not k.startswith("_")]),
        },
    }


@app.get("/meta/methodology")
def methodology():
    return {
        "chain": "tokens (exact, provider usage) × Wh-per-1k-token factors (sourced, in/out separate) × PUE → kWh (estimated) × grid intensity gCO2/kWh (Electricity Maps ← grid operators) → gCO2",
        "energy_factors": config.ENERGY_FACTORS,
        "price_table": config.PRICE_TABLE,
        "fallback_intensity": config.FALLBACK_INTENSITY,
        "pue": config.PUE,
        "scope": [
            "operational inference only — training/embodied emissions out of scope (SCI M=0, declared)",
            "average grid intensity, not marginal (marginal requires WattTime PRO)",
            "assumed default datacenter region per provider; placement decisions are simulated (real region selection exists on Bedrock/Azure)",
            "closed-model parameter counts are stated assumptions (see params_known flags)",
            "sensitivity: savings are ratio-driven by the model-size gap; ±2× factor error barely moves the reduction percentage",
        ],
        "labels": ["estimated", "exact", "live", "cached", "snapshot", "fallback", "replay"],
    }


# --- P1 TODO (spec 06 / task P1-M3): ---
@app.post("/route")
def route_endpoint():
    raise HTTPException(501, detail="P1-M3: wire to backend.router.route (P2, h8 sync)")


@app.post("/benchmark/run")
def benchmark_run():
    raise HTTPException(501, detail="P1-M3: background task → backend.benchmark.harness (P3)")


@app.get("/runs")
def list_runs():
    raise HTTPException(501, detail="P1-M3: list persisted runs from db.store")


@app.get("/runs/{run_id}")
def get_run(run_id: str, after_seq: int = 0):
    raise HTTPException(501, detail="P1-M3: polling contract per spec 06")


@app.get("/report/{run_id}")
def get_report(run_id: str):
    raise HTTPException(501, detail="P1-M3: serve persisted report_json")
