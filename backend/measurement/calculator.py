"""The impact chain (spec §0): tokens → estimated kWh → gCO₂ at a zone's
intensity, plus exact cost from the provider price sheet."""
from backend import config
from backend.measurement import carbon, energy


def cost_usd(model_key: str, tokens_in: int, tokens_out: int) -> float:
    row = config.PRICE_TABLE.get(model_key)
    if row is None:
        raise KeyError(f"No price row for {model_key!r} in data/price_table.json")
    return (tokens_in / 1e6) * row["usd_per_1m_in"] + (tokens_out / 1e6) * row["usd_per_1m_out"]


def measure(model_key: str, tokens_in: int, tokens_out: int, zone: str) -> dict:
    """Full per-call impact record. Energy/carbon are estimates (labeled);
    cost is exact; the local wall-clock intensity is stored for auditability."""
    e = energy.estimate_wh(model_key, tokens_in, tokens_out)
    intensity = carbon.get_intensity(zone)
    return {
        "model_key": model_key,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "wh": e["wh"],
        "energy_label": e["label"],
        "params_known": e["params_known"],
        "zone": zone,
        "gco2_per_kwh": intensity["gco2_per_kwh"],
        "intensity_label": intensity["label"],
        "gco2": e["kwh"] * intensity["gco2_per_kwh"],
        "cost_usd": cost_usd(model_key, tokens_in, tokens_out),
    }
