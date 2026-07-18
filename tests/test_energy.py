"""Energy estimator (spec 03 D2): tokens × factors × PUE, labeled, loud on unknowns.

Math tests use a synthetic factor row so P1 can re-verify real values against
EcoLogits without touching tests — we pin the FORMULA, not the data.
"""
import pytest

from backend import config
from backend.measurement import energy

SYNTH = {
    "test:model": {
        "wh_per_1k_in": 0.1, "wh_per_1k_out": 1.0,
        "params_known": True, "source": "synthetic", "source_date": "2026-07-18",
    }
}


@pytest.fixture
def synth_factors(monkeypatch):
    monkeypatch.setattr(config, "ENERGY_FACTORS", SYNTH)
    monkeypatch.setattr(config, "PUE", 1.5)


def test_formula_hand_computed(synth_factors):
    """E = (in/1000×f_in + out/1000×f_out) × PUE, checked against a by-hand value.
    2000 in × 0.1 + 500 out × 1.0 = 0.2 + 0.5 = 0.7 chip Wh; × PUE 1.5 = 1.05 Wh.
    If this breaks, every carbon number in the product is wrong."""
    r = energy.estimate_wh("test:model", 2000, 500)
    assert r["chip_wh"] == pytest.approx(0.7)
    assert r["wh"] == pytest.approx(1.05)
    assert r["kwh"] == pytest.approx(0.00105)


def test_output_tokens_dominate(synth_factors):
    """The same token count as output must cost 10× the input cost with these
    factors — guards against summing tokens_in+tokens_out into one bucket, which
    would understate decode-heavy (long answer) queries."""
    as_input = energy.estimate_wh("test:model", 1000, 0)["wh"]
    as_output = energy.estimate_wh("test:model", 0, 1000)["wh"]
    assert as_output == pytest.approx(10 * as_input)


def test_zero_tokens_zero_energy(synth_factors):
    """A call that produced no tokens (e.g., hard failure before generation)
    contributes zero energy — not NaN, not a crash. Failed calls stay in totals
    (spec 05 guardrails) so this path really runs."""
    assert energy.estimate_wh("test:model", 0, 0)["wh"] == 0.0


def test_always_labeled_estimated(synth_factors):
    """D2: 'everything labeled estimated — no exceptions.' The label is what keeps
    the demo honest; if it ever goes missing the UI renders an unlabeled number."""
    assert energy.estimate_wh("test:model", 10, 10)["label"] == "estimated"


def test_unknown_model_is_loud(synth_factors):
    """Cross-cutting rule (spec 01): never guess silently. An unrecognized model
    must raise and name the file to fix — a silent default factor would fabricate
    carbon numbers for a model we never analyzed."""
    with pytest.raises(energy.UnknownModelError, match="energy_factors.json"):
        energy.estimate_wh("nope:ghost-model", 10, 10)
