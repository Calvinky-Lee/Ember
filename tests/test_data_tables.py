"""Data-table integrity — the tables ARE the methodology (spec 03, KR3.1/3.3).

A malformed or missing row doesn't crash loudly at startup; it would surface as a
wrong number on a judge's screen. These tests make table mistakes fail in CI
instead. Values are free to change (P1 verifies them against EcoLogits/price
pages); shape and consistency are not.
"""
from backend import config


def _rows(table):
    return {k: v for k, v in table.items() if not k.startswith("_")}


def test_every_energy_row_is_complete_and_sane():
    """Each factor row must have positive in/out factors, a source, a date, and an
    explicit params_known flag. A row without a source can't be defended in the
    methodology view (Deloitte 30%); a zero/negative factor would silently zero
    out a model's carbon."""
    for key, row in _rows(config.ENERGY_FACTORS).items():
        assert row["wh_per_1k_in"] > 0, key
        assert row["wh_per_1k_out"] > 0, key
        assert isinstance(row["params_known"], bool), key
        assert row.get("source"), f"{key} has no source — methodology view breaks"
        assert row.get("source_date"), key


def test_output_tokens_cost_more_energy_than_input():
    """Decode is ~an order of magnitude costlier per token than prefill (spec 03
    'prefill vs decode'). If someone swaps in/out while editing the table, every
    downstream number inverts — this catches the transposition."""
    for key, row in _rows(config.ENERGY_FACTORS).items():
        assert row["wh_per_1k_out"] > row["wh_per_1k_in"], f"{key}: in/out transposed?"


def test_every_price_row_positive():
    """Cost is the 'exact, zero caveats' number (D7). A zero price would fake
    infinite savings."""
    for key, row in _rows(config.PRICE_TABLE).items():
        assert row["usd_per_1m_in"] > 0, key
        assert row["usd_per_1m_out"] > 0, key


def test_ladder_and_judge_models_have_factor_and_price_rows():
    """The real integration bug this suite exists for: adding a model to the
    ladder (or changing the judge) without adding its table rows. energy.py and
    calculator.py raise at runtime — this makes it fail before the demo instead."""
    needed = set(config.MODEL_LADDER.values()) | {config.JUDGE_MODEL}
    for model_key in needed:
        assert model_key in config.ENERGY_FACTORS, f"{model_key} missing energy factors"
        assert model_key in config.PRICE_TABLE, f"{model_key} missing price row"


def test_all_configured_zones_have_fallback_intensities():
    """D18/spec 05: the demo must run with the network dead. Every zone we might
    ever attribute to (candidates + the baseline's assumed region) needs a static
    fallback factor, or airplane mode raises KeyError mid-demo."""
    for zone in [*config.CARBON_ZONES, config.BASELINE_ZONE]:
        assert zone in config.FALLBACK_INTENSITY, f"{zone} has no fallback intensity"
        assert config.FALLBACK_INTENSITY[zone] > 0


def test_frontier_tier_is_opus_parity_target():
    """Project requirement: the hard tier and baseline arm are the latest Opus
    (spec 00 D1/D12). If someone flips MODEL_HARD to a cheaper default and forgets,
    the parity claim silently changes meaning."""
    assert config.MODEL_LADDER["hard"].startswith("anthropic:claude-opus"), (
        "MODEL_HARD is not Opus — if intentional (no Anthropic key fallback), "
        "update this test and spec 00 in the same commit"
    )
