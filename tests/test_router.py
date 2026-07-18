"""Router (spec 04): classifier, quality gate (D19 hybrid), and route() orchestration.

Testing strategy note: classifier/quality_gate/route tests mock at the collaborator
boundary (registry.chat, classifier.classify, quality_gate.verify/check_confidence)
rather than faking httpx responses — the wire-protocol contract itself is already
pinned down in test_providers.py. This keeps these tests about ORCHESTRATION logic
(who gets called, in what order, what ends up in calls[]/totals) without re-deriving
provider response shapes. Still no network, no real keys, deterministic.
"""
import math

import pytest

from backend import config
from backend.providers.base import ChatResult
from backend.router import classifier, quality_gate, route


def _chat_result(model_key, *, confidence=None, tokens_in=10, tokens_out=5,
                  latency_ms=50.0, text="answer"):
    return ChatResult(text=text, tokens_in=tokens_in, tokens_out=tokens_out,
                       latency_ms=latency_ms, model_key=model_key, confidence=confidence)


def _chat_queue(results):
    """registry.chat fake that returns queued results in call order — valid here
    because each test controls exactly how many answer-calls the loop will make."""
    it = iter(results)

    def fake(model_key, messages, **kw):
        return next(it)

    return fake


def _no_model_calls(*_a, **_kw):
    raise AssertionError("registry.chat must not be called on this path")


def _judge_verdict(score, passed, model_key=None, tokens_in=8, tokens_out=4, latency_ms=40.0):
    """A plausible quality_gate.verify() return — judge_impact shaped like
    measurement.calculator.measure()'s output plus the latency_ms verify() adds."""
    model_key = model_key or config.JUDGE_MODEL
    return {
        "score": score,
        "pass": passed,
        "judge_model": model_key,
        "judge_impact": {
            "model_key": model_key, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "wh": 0.001, "energy_label": "estimated", "params_known": False,
            "zone": "SE", "gco2_per_kwh": 25, "intensity_label": "fallback",
            "gco2": 0.000025, "cost_usd": 0.00001, "latency_ms": latency_ms,
        },
        "raw": '{"score": %s}' % score,
    }


# --- classifier.py --------------------------------------------------------------

def test_tier_for_score_boundaries():
    """Spec 04: score<=LOW -> trivial, score>=HIGH -> hard, the band between is
    'unsure' (None) — the exact boundary is what routes queries into the free
    LLM overhead call vs. resolving for free."""
    assert classifier._tier_for_score(0) == "trivial"
    assert classifier._tier_for_score(classifier._LOW) == "trivial"
    assert classifier._tier_for_score(classifier._LOW + 1) is None
    assert classifier._tier_for_score(classifier._HIGH) == "hard"


def test_parse_difficulty_digit_rounds_up_when_unparseable():
    """Unsure-band overhead call ('rate 1-3') returning garbage must round UP to
    moderate, never silently default to trivial — misclassifying down is the one
    unsafe direction (D-series: gate protects quality, never protects savings)."""
    assert classifier._parse_difficulty_digit("1") == "trivial"
    assert classifier._parse_difficulty_digit("2") == "moderate"
    assert classifier._parse_difficulty_digit("3") == "hard"
    assert classifier._parse_difficulty_digit("no idea") == "moderate"


def test_classify_confident_trivial_never_calls_a_model(monkeypatch):
    """A query the heuristics are confident about must resolve for free — the
    whole point of two-stage classification is not spending a call when we
    don't need one (spec 04 classifier stage 1)."""
    monkeypatch.setattr(classifier, "_heuristic_score", lambda q: (0, {}))
    from backend.providers import registry
    monkeypatch.setattr(registry, "chat", _no_model_calls)

    result = classifier.classify("What is 2+2?")
    assert result["tier"] == "trivial"
    assert result["overhead_call"] is None


def test_classify_confident_hard_never_calls_a_model(monkeypatch):
    monkeypatch.setattr(classifier, "_heuristic_score", lambda q: (5, {}))
    from backend.providers import registry
    monkeypatch.setattr(registry, "chat", _no_model_calls)

    result = classifier.classify("Prove that sqrt(2) is irrational, step by step.")
    assert result["tier"] == "hard"
    assert result["overhead_call"] is None


def test_classify_unsure_band_calls_trivial_model_and_returns_the_call(monkeypatch):
    """Stage 2 (spec 04): unsure band spends exactly one cheap call, and route()
    needs that call back (as overhead_call) so its cost/energy is booked (D4)."""
    monkeypatch.setattr(classifier, "_heuristic_score", lambda q: (2, {}))
    from backend.providers import registry
    fake_result = _chat_result(config.MODEL_LADDER["trivial"], text="2")
    monkeypatch.setattr(registry, "chat", lambda *a, **kw: fake_result)

    result = classifier.classify("some ambiguous query")
    assert result["tier"] == "moderate"
    assert result["overhead_call"] is fake_result


# --- quality_gate.py --------------------------------------------------------------

def test_check_confidence_pass_above_floor():
    cr = _chat_result("groq:llama-3.1-8b-instant", confidence=config.CONFIDENCE_FLOOR + 0.1)
    verdict = quality_gate.check_confidence(cr)
    assert verdict["pass"] is True
    assert verdict["method"] == "self_confidence"


def test_check_confidence_fail_below_floor():
    cr = _chat_result("groq:llama-3.1-8b-instant", confidence=config.CONFIDENCE_FLOOR - 0.1)
    assert quality_gate.check_confidence(cr)["pass"] is False


def test_check_confidence_missing_confidence_fails_safe():
    """Missing/NaN confidence (e.g. provider didn't honor logprobs) must fail,
    not pass-by-default — route() treats this specifically as 'fall back to
    verify()', so the None must be visible in the verdict, not swallowed."""
    cr = _chat_result("groq:llama-3.1-8b-instant", confidence=None)
    verdict = quality_gate.check_confidence(cr)
    assert verdict["pass"] is False
    assert verdict["score"] is None

    cr_nan = _chat_result("groq:llama-3.1-8b-instant", confidence=math.nan)
    assert quality_gate.check_confidence(cr_nan)["pass"] is False


def test_verify_pass(monkeypatch):
    from backend.providers import registry
    monkeypatch.setattr(registry, "chat", lambda *a, **kw: _chat_result(
        config.JUDGE_MODEL, text='{"score": 0.95}'))

    verdict = quality_gate.verify("q", "a", "SE")
    assert verdict["pass"] is True
    assert verdict["judge_model"] == config.JUDGE_MODEL
    assert verdict["judge_impact"]["tokens_in"] == 10  # single call, no retry


def test_verify_retries_once_on_unparseable_and_books_both_calls(monkeypatch):
    """D4: the first (wasted) attempt still cost tokens/energy — the retry must
    not make that call invisible to totals (spec 04: 'strict-retry once')."""
    from backend.providers import registry
    responses = _chat_queue([
        _chat_result(config.JUDGE_MODEL, text="not json", tokens_in=10, tokens_out=4),
        _chat_result(config.JUDGE_MODEL, text='{"score": 0.9}', tokens_in=12, tokens_out=6),
    ])
    monkeypatch.setattr(registry, "chat", responses)

    verdict = quality_gate.verify("q", "a", "SE")
    assert verdict["pass"] is True
    assert verdict["judge_impact"]["tokens_in"] == 22  # 10 + 12, both attempts booked
    assert verdict["judge_impact"]["tokens_out"] == 10


def test_verify_still_unparseable_after_retry_fails_safe(monkeypatch):
    from backend.providers import registry
    monkeypatch.setattr(registry, "chat", lambda *a, **kw: _chat_result(
        config.JUDGE_MODEL, text="garbage"))

    verdict = quality_gate.verify("q", "a", "SE")
    assert verdict["pass"] is False
    assert verdict["score"] == 0.0


def test_verify_falls_back_to_hard_tier_judge_when_key_missing(monkeypatch):
    """Spec 04: judge key unavailable -> fallback judges one tier above the
    answering model; verify() is moderate-only (D19), so that's always hard/Opus."""
    from backend.providers import registry
    from backend.providers.base import ProviderError

    def fake_chat(model_key, messages, **kw):
        if model_key == config.JUDGE_MODEL:
            raise ProviderError("GEMINI_API_KEY is not set")
        return _chat_result(model_key, text='{"score": 0.9}')

    monkeypatch.setattr(registry, "chat", fake_chat)
    verdict = quality_gate.verify("q", "a", "SE")
    assert verdict["judge_model"] == config.MODEL_LADDER["hard"]
    assert verdict["pass"] is True


# --- route.py --------------------------------------------------------------------

def _mock_classifier(monkeypatch, tier):
    monkeypatch.setattr(
        classifier, "classify",
        lambda query: {"tier": tier, "signals": {}, "latency_ms": 1.0, "overhead_call": None},
    )


def _assert_totals_match(result):
    for key in ("gco2", "cost_usd", "wh", "latency_ms"):
        assert result["totals"][key] == pytest.approx(sum(c.get(key, 0.0) for c in result["calls"]))


def test_route_trivial_pass_is_a_single_call_no_judge(monkeypatch):
    """Spec 04 acceptance: a confident trivial pass must cost exactly one call —
    the entire point of D19 is that this path never pays for a judge."""
    _mock_classifier(monkeypatch, "trivial")
    from backend.providers import registry
    high_conf = _chat_result(config.MODEL_LADDER["trivial"], confidence=0.99, text="4")
    monkeypatch.setattr(registry, "chat", _chat_queue([high_conf]))

    result = route.route("What is 2+2?")
    assert result["tier_first"] == result["tier_final"] == "trivial"
    assert len(result["calls"]) == 1
    assert result["calls"][0]["role"] == "answer"
    assert result["escalations"] == []
    _assert_totals_match(result)


def test_route_low_confidence_escalates_to_moderate(monkeypatch):
    _mock_classifier(monkeypatch, "trivial")
    from backend.providers import registry
    low_conf = _chat_result(config.MODEL_LADDER["trivial"], confidence=0.1, text="4")
    moderate_answer = _chat_result(config.MODEL_LADDER["moderate"], confidence=None, text="4")
    monkeypatch.setattr(registry, "chat", _chat_queue([low_conf, moderate_answer]))
    monkeypatch.setattr(quality_gate, "verify", lambda q, a, z: _judge_verdict(0.9, True))

    result = route.route("some query")
    assert result["tier_first"] == "trivial"
    assert result["tier_final"] == "moderate"
    assert len(result["escalations"]) == 1
    assert result["escalations"][0] == {"from": "trivial", "to": "moderate", "score": 0.1}
    assert [c["role"] for c in result["calls"]] == ["answer", "answer", "judge"]
    _assert_totals_match(result)


def test_route_no_logprobs_support_falls_back_to_verify_at_trivial_tier(monkeypatch):
    """Spec 04 edge case: confidence is None because the model/provider doesn't
    support logprobs -> fall back to the judge for THAT tier, not a tier escalation."""
    _mock_classifier(monkeypatch, "trivial")
    from backend.providers import registry
    no_logprobs = _chat_result(config.MODEL_LADDER["trivial"], confidence=None, text="4")
    monkeypatch.setattr(registry, "chat", _chat_queue([no_logprobs]))
    monkeypatch.setattr(quality_gate, "verify", lambda q, a, z: _judge_verdict(0.9, True))

    result = route.route("some query")
    assert result["tier_final"] == "trivial"
    assert result["escalations"] == []
    assert [c["role"] for c in result["calls"]] == ["answer", "judge"]
    assert result["calls"][1]["fallback"] == "no_logprobs"
    _assert_totals_match(result)


def test_route_hard_prompt_lands_on_opus_unjudged(monkeypatch):
    _mock_classifier(monkeypatch, "hard")
    from backend.providers import registry
    hard_answer = _chat_result(config.MODEL_LADDER["hard"], confidence=None, text="proof")
    monkeypatch.setattr(registry, "chat", _chat_queue([hard_answer]))

    result = route.route("Prove that sqrt(2) is irrational")
    assert result["tier_first"] == result["tier_final"] == "hard"
    assert result["escalations"] == []
    assert len(result["calls"]) == 1
    _assert_totals_match(result)


def test_route_forced_fail_walks_full_ladder_and_terminates_at_hard(monkeypatch):
    """Spec 04 acceptance: with both floors effectively impossible to satisfy,
    every query still terminates at hard — no infinite loop, ladder runs out."""
    _mock_classifier(monkeypatch, "trivial")
    from backend.providers import registry
    trivial_answer = _chat_result(config.MODEL_LADDER["trivial"], confidence=0.99, text="x")
    moderate_answer = _chat_result(config.MODEL_LADDER["moderate"], confidence=None, text="x")
    hard_answer = _chat_result(config.MODEL_LADDER["hard"], confidence=None, text="x")
    monkeypatch.setattr(registry, "chat", _chat_queue([trivial_answer, moderate_answer, hard_answer]))
    monkeypatch.setattr(config, "CONFIDENCE_FLOOR", 1.01)
    monkeypatch.setattr(quality_gate, "verify", lambda q, a, z: _judge_verdict(0.5, False))

    result = route.route("some query")
    assert result["tier_final"] == "hard"
    assert len(result["escalations"]) == 2
    assert [e["to"] for e in result["escalations"]] == ["moderate", "hard"]
    _assert_totals_match(result)
