"""Spend estimator (task P1-M4, spec 05): the up-front number the harness quotes
before spending a cent of Opus credit. Cost is exact price-sheet math; only the
token averages are assumed — so the estimate must track the price table exactly."""
import pytest

from backend import config
from backend.measurement import spend


@pytest.fixture
def synth_prices(monkeypatch):
    monkeypatch.setattr(config, "PRICE_TABLE", {
        "anthropic:claude-opus-4-8": {"usd_per_1m_in": 15.0, "usd_per_1m_out": 75.0},
        "gemini:gemini-2.5-flash": {"usd_per_1m_in": 0.3, "usd_per_1m_out": 2.5},
    })
    monkeypatch.setattr(config, "MODEL_LADDER",
                        {**config.MODEL_LADDER, "hard": "anthropic:claude-opus-4-8"})
    monkeypatch.setattr(config, "JUDGE_MODEL", "gemini:gemini-2.5-flash")


def test_arm_a_is_exact_opus_price_math(synth_prices):
    """Arm A = every call → Opus. 10 tasks × K=1, 1000 in + 1000 out each:
    per call = 1000/1e6×15 + 1000/1e6×75 = $0.015 + $0.075 = $0.09; ×10 = $0.90."""
    est = spend.estimate_spend(10, k=1, avg_tokens_in=1000, avg_tokens_out=1000)
    assert est["calls_per_arm"] == 10
    assert est["arm_a_usd"] == pytest.approx(0.90)


def test_arm_b_ceiling_exceeds_arm_a_by_judge_cost(synth_prices):
    """Arm B worst case adds a judge pass on top of a top-tier answer, so its ceiling
    is strictly greater than Arm A — the confirm prompt must never under-quote."""
    est = spend.estimate_spend(10, k=1, avg_tokens_in=1000, avg_tokens_out=1000)
    assert est["arm_b_ceiling_usd"] > est["arm_a_usd"]
    assert est["total_ceiling_usd"] == pytest.approx(est["arm_a_usd"] + est["arm_b_ceiling_usd"])


def test_estimate_carries_provenance_label(synth_prices):
    """Like every Ember number, the estimate is labeled — cost exact, tokens assumed."""
    est = spend.estimate_spend(5)
    assert "exact" in est["label"]
    assert "note" in est["assumptions"]
