"""Electricity Maps client with the spec's degradation ladder (§5):
live API → 60s in-memory cache → last-good disk snapshot → static fallback
factors. Every intensity carries a label so the UI can render provenance."""
import json
import time
from pathlib import Path

import httpx

from backend import config

BASE = "https://api.electricitymap.org/v3"
SNAPSHOT_FILE = config.SNAPSHOTS / "intensity.json"

_cache: dict[str, tuple[float, dict]] = {}  # zone → (fetched_monotonic, result)


def _snapshot_load() -> dict:
    if SNAPSHOT_FILE.exists():
        with open(SNAPSHOT_FILE) as f:
            return json.load(f)
    return {}


def _snapshot_save(zone: str, result: dict) -> None:
    config.SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snap = _snapshot_load()
    snap[zone] = result
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(snap, f, indent=2)


def get_intensity(zone: str) -> dict:
    """→ {zone, gco2_per_kwh, label: live|cached|snapshot|fallback, fetched_at}"""
    cached = _cache.get(zone)
    if cached and time.monotonic() - cached[0] < config.EM_CACHE_S:
        return {**cached[1], "label": "cached"}

    if config.ELECTRICITYMAPS_TOKEN:
        try:
            resp = httpx.get(
                f"{BASE}/carbon-intensity/latest",
                params={"zone": zone},
                headers={"auth-token": config.ELECTRICITYMAPS_TOKEN},
                timeout=10.0,
            )
            if resp.status_code == 200:
                body = resp.json()
                intensity = body.get("carbonIntensity")
                if intensity is not None:
                    result = {
                        "zone": zone,
                        "gco2_per_kwh": float(intensity),
                        "label": "live",
                        "fetched_at": body.get("datetime", ""),
                    }
                    _cache[zone] = (time.monotonic(), result)
                    _snapshot_save(zone, result)
                    return result
        except httpx.HTTPError:
            pass  # fall through the degradation ladder

    snap = _snapshot_load().get(zone)
    if snap:
        return {**snap, "label": "snapshot"}

    fallback = config.FALLBACK_INTENSITY.get(zone)
    if fallback is None:
        raise KeyError(f"Zone {zone!r} has no fallback factor in data/fallback_intensity.json")
    return {"zone": zone, "gco2_per_kwh": float(fallback), "label": "fallback", "fetched_at": ""}


def greenest_zone(zones: list[str] | None = None) -> dict:
    """Lowest-intensity candidate right now — the placement decision input (D5).
    Zones that error out are dropped from the candidate set for this cycle."""
    candidates = []
    for zone in zones or config.CARBON_ZONES:
        try:
            candidates.append(get_intensity(zone))
        except KeyError:
            continue
    if not candidates:
        raise RuntimeError("No carbon zones resolvable — check CARBON_ZONES and fallback table")
    return min(candidates, key=lambda c: c["gco2_per_kwh"])
