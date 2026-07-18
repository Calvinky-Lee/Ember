"""Energy estimation: tokens × per-token factors × PUE → Wh.
Every result is labeled 'estimated' — Ember never presents energy as measured
(the compute happens in a provider datacenter we cannot meter). Spec D2/§4.2."""
from backend import config


class UnknownModelError(Exception):
    pass


def estimate_wh(model_key: str, tokens_in: int, tokens_out: int) -> dict:
    row = config.ENERGY_FACTORS.get(model_key)
    if row is None:
        raise UnknownModelError(
            f"No energy factors for {model_key!r} — add a sourced row to "
            f"data/energy_factors.json (never default silently)"
        )
    chip_wh = (tokens_in / 1000) * row["wh_per_1k_in"] + (tokens_out / 1000) * row["wh_per_1k_out"]
    wh = chip_wh * config.PUE
    return {
        "wh": wh,
        "kwh": wh / 1000,
        "chip_wh": chip_wh,
        "pue": config.PUE,
        "label": "estimated",
        "params_known": row.get("params_known", False),
        "factor_source": row.get("source", ""),
    }
