"""Phase-0 gate (spec §6, hour 0–2): one real API call printed as the full
impact chain. Run:  uv run python -m backend.smoke "What is the capital of France?"
Works without an Electricity Maps token (labeled fallback intensities)."""
import sys

from backend import config
from backend.measurement import calculator, carbon
from backend.providers import registry
from backend.providers.base import ProviderError


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "What is the capital of France?"
    model_key = config.MODEL_LADDER["trivial"]

    print("Ember Phase-0 gate — one real call through the impact chain\n")
    try:
        result = registry.chat(model_key, [{"role": "user", "content": query}], max_tokens=256)
    except ProviderError as e:
        print(f"  BLOCKED: {e}")
        return 1

    pick = carbon.greenest_zone()
    m = calculator.measure(result.model_key, result.tokens_in, result.tokens_out, pick["zone"])

    zones = ",".join(config.CARBON_ZONES)
    print(f'  query      "{query}"')
    print(f"  model      {m['model_key']}")
    print(f"  tokens     {m['tokens_in']} in / {m['tokens_out']} out  (provider usage field, exact)")
    print(f"  energy     ~{m['wh']:.4f} Wh  ({m['energy_label']}: factor table × PUE {config.PUE})")
    print(f"  zone       {m['zone']} @ {m['gco2_per_kwh']:.0f} gCO2/kWh  [{m['intensity_label']}]  (greenest of {zones})")
    print(f"  carbon     ~{m['gco2']:.5f} gCO2  (estimated)")
    print(f"  cost       ${m['cost_usd']:.7f}  (exact, provider price sheet)")
    print(f"  latency    {result.latency_ms:.0f} ms")
    answer = result.text.strip().replace("\n", " ")
    print(f'  answer     "{answer[:120]}{"…" if len(answer) > 120 else ""}"')
    print("\n  Gate passed: this call used "
          f"~{m['tokens_in'] + m['tokens_out']} tokens → ~{m['wh']:.4f} Wh → ~{m['gco2']:.5f} gCO2 (estimated).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
