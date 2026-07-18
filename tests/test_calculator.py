"""Impact calculator (spec 03 §4): the record every dashboard number comes from.

gCO2 must be exactly kWh × intensity; cost must be exactly the price-sheet math
(D7: 'the number that needs zero caveats'); labels must survive the trip.
"""
import pytest

from backend import config
from backend.measurement import calculator, carbon


@pytest.fixture
def synth_tables(monkeypatch):
    monkeypatch.setattr(config, "ENERGY_FACTORS", {
        "test:model": {"wh_per_1k_in": 0.1, "wh_per_1k_out": 1.0,
                       "params_known": True, "source": "synthetic", "source_date": "x"},
    })
    monkeypatch.setattr(config, "PRICE_TABLE", {
        "test:model": {"usd_per_1m_in": 2.0, "usd_per_1m_out": 10.0},
    })
    monkeypatch.setattr(config, "PUE", 1.0)  # PUE=1 → chip energy == billed energy


def test_cost_is_exact_price_sheet_math(synth_tables):
    """500k input @ $2/1M + 100k output @ $10/1M = $1.00 + $1.00 = $2.00, to the
    cent. The cost headline is the one claim with no caveats — it must be penny-
    perfect, not approximately right."""
    assert calculator.cost_usd("test:model", 500_000, 100_000) == pytest.approx(2.0)


def test_gco2_is_kwh_times_intensity(synth_tables, monkeypatch):
    """The core equation of the whole project (spec 00 impact chain), hand-checked:
    1000 out tokens × 1.0 Wh/1k = 1 Wh = 0.001 kWh; × 400 gCO2/kWh = 0.4 g."""
    monkeypatch.setattr(carbon, "get_intensity",
                        lambda zone: {"zone": zone, "gco2_per_kwh": 400.0,
                                      "label": "live", "fetched_at": "T"})
    m = calculator.measure("test:model", 0, 1000, "PL")
    assert m["gco2"] == pytest.approx(0.4)


def test_labels_propagate_end_to_end(synth_tables, monkeypatch):
    """KR3.2 depends on labels surviving from source to record: energy must say
    'estimated', intensity must carry the ladder rung it actually came from.
    A dropped label = an unlabeled number in front of a judge."""
    monkeypatch.setattr(carbon, "get_intensity",
                        lambda zone: {"zone": zone, "gco2_per_kwh": 100.0,
                                      "label": "snapshot", "fetched_at": "T"})
    m = calculator.measure("test:model", 100, 100, "SE")
    assert m["energy_label"] == "estimated"
    assert m["intensity_label"] == "snapshot"
    assert m["params_known"] is True


def test_unknown_model_in_price_table_is_loud(synth_tables):
    """Same never-guess-silently rule as energy factors, for the price side:
    a model without a price row must raise naming the file, not price at $0
    (which would inflate the savings claim)."""
    with pytest.raises(KeyError, match="price_table.json"):
        calculator.cost_usd("nope:ghost", 10, 10)
