"""Central config: env, model ladder, zones, thresholds, data file paths."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "snapshots"

load_dotenv(ROOT / ".env")

TIERS = ("trivial", "moderate", "hard")

MODEL_LADDER = {
    "trivial": os.getenv("MODEL_TRIVIAL", "groq:llama-3.1-8b-instant"),
    "moderate": os.getenv("MODEL_MODERATE", "groq:llama-3.3-70b-versatile"),
    "hard": os.getenv("MODEL_HARD", "anthropic:claude-opus-4-8"),
}

# Independent-family judge (Gemini) — no ladder model grades its own siblings.
# quality_gate falls back to tier_plus_one when this key/model is unavailable.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gemini:gemini-2.5-flash")

BASELINE_ZONE = os.getenv("BASELINE_ZONE", "US-MIDA-PJM")
CARBON_ZONES = [z.strip() for z in os.getenv("CARBON_ZONES", "SE,FR,US-CAL-CISO,CA-ON,PL").split(",") if z.strip()]
QUALITY_FLOOR = float(os.getenv("QUALITY_FLOOR", "0.85"))
EM_CACHE_S = int(os.getenv("EM_CACHE_S", "60"))
PUE = float(os.getenv("PUE_DEFAULT", "1.2"))
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "4"))

ELECTRICITYMAPS_TOKEN = os.getenv("ELECTRICITYMAPS_TOKEN", "")


def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


ENERGY_FACTORS = _load_json(DATA / "energy_factors.json")
PRICE_TABLE = _load_json(DATA / "price_table.json")
FALLBACK_INTENSITY = _load_json(DATA / "fallback_intensity.json")


def next_tier(tier: str) -> str | None:
    """One rung up the ladder, None at the top (escalation stops here)."""
    i = TIERS.index(tier)
    return TIERS[i + 1] if i + 1 < len(TIERS) else None
