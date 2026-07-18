"""Config & ladder mechanics (spec 01) — small, but the escalation safety
invariants (D10) start here."""
import pytest

from backend import config


def test_ladder_covers_exactly_the_three_tiers():
    """route() indexes MODEL_LADDER by classifier output — a missing or extra
    tier key is a KeyError at 3am. The ladder and TIERS must agree exactly."""
    assert set(config.MODEL_LADDER) == set(config.TIERS)


def test_next_tier_walks_up_and_terminates():
    """D10 termination proof, unit-sized: escalation climbs one rung at a time
    and next_tier at the top is None — the 'hard stop at Opus' that makes
    infinite escalation loops impossible by construction."""
    assert config.next_tier("trivial") == "moderate"
    assert config.next_tier("moderate") == "hard"
    assert config.next_tier("hard") is None


def test_quality_floor_is_a_sane_probability():
    """The floor is a 0–1 rubric score (spec 04). A stray '85' in .env instead of
    '0.85' would make EVERY answer fail the gate → 100% escalation → zero savings,
    and nobody would know why."""
    assert 0.0 < config.QUALITY_FLOOR <= 1.0
