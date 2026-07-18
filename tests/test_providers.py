"""Provider layer (spec 02): uniform contract over three wire protocols.

The invariant that matters most: token counts come from the provider's usage
field or the result is INVALID (D2/§4.1) — because every downstream number
(energy, carbon, cost) multiplies off those counts.
"""
import pytest

from backend.providers import registry
from backend.providers.base import MissingUsageError, ProviderError
from backend.providers.openai_compat import PROVIDERS as OAI_PROVIDERS


def _fake_post(monkeypatch, module, response):
    """Install a fake httpx.post on a provider module; returns captured kwargs."""
    captured = {}

    def fake(url, **kw):
        captured.update(kw, url=url)
        return response

    monkeypatch.setattr(module.httpx, "post", fake)
    return captured


# --- registry -----------------------------------------------------------------

def test_unknown_provider_is_loud():
    """A typo'd model key ('gorq:llama...') must fail immediately listing valid
    providers — not reach the network, not fall back to some default vendor."""
    with pytest.raises(ProviderError, match="anthropic"):
        registry.chat("gorq:llama-3.1-8b-instant", [])


def test_bare_provider_without_model_is_loud():
    """'groq' with no ':model' part is a malformed ladder entry (bad .env edit) —
    must be caught at the registry, not sent as an empty model name."""
    with pytest.raises(ProviderError):
        registry.chat("groq", [])


# --- OpenAI-compatible (groq / openai / gemini) ---------------------------------

def test_missing_key_names_the_env_var(monkeypatch):
    """Spec 02 acceptance: the missing-key error must say WHICH env var and where
    to get one — at 3am mid-hackathon, 'KeyError: None' costs 20 minutes,
    'GROQ_API_KEY is not set — console.groq.com/keys' costs 20 seconds."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="GROQ_API_KEY"):
        registry.chat("groq:llama-3.1-8b-instant", [{"role": "user", "content": "hi"}])


def test_successful_call_maps_uniform_contract(monkeypatch, fake_response):
    """Happy path: text, EXACT usage tokens, and the model_key that indexes the
    factor/price tables must all round-trip. model_key must be 'provider:model' —
    a bare model name would miss every table row."""
    import backend.providers.openai_compat as oc
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    _fake_post(monkeypatch, oc, fake_response(200, {
        "choices": [{"message": {"content": "Paris"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
    }))

    r = registry.chat("groq:llama-3.1-8b-instant", [{"role": "user", "content": "capital of France?"}])
    assert (r.text, r.tokens_in, r.tokens_out) == ("Paris", 12, 3)
    assert r.model_key == "groq:llama-3.1-8b-instant"


def test_missing_usage_field_invalidates_result(monkeypatch, fake_response):
    """THE provider-layer honesty rule: a 200 response without usage must raise
    MissingUsageError, never estimate tokens locally — a guessed token count
    fabricates the energy, carbon, and cost of that call (spec 05 edge case:
    'never guess tokens silently')."""
    import backend.providers.openai_compat as oc
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    _fake_post(monkeypatch, oc, fake_response(200, {
        "choices": [{"message": {"content": "Paris"}}],
    }))

    with pytest.raises(MissingUsageError):
        registry.chat("groq:llama-3.1-8b-instant", [{"role": "user", "content": "hi"}])


def test_http_429_surfaces_status_for_backoff(monkeypatch, fake_response):
    """Rate limits are certain during the benchmark (Opus, spec 05). The harness's
    backoff needs to SEE the 429 — the provider layer must surface it in the
    error, not swallow it into a generic failure."""
    import backend.providers.openai_compat as oc
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    _fake_post(monkeypatch, oc, fake_response(429, {"error": "rate limited"}))

    with pytest.raises(ProviderError, match="429"):
        registry.chat("groq:llama-3.1-8b-instant", [{"role": "user", "content": "hi"}])


def test_gemini_rides_openai_compatible_path():
    """The judge (Gemini, D9) uses Google's OpenAI-compatible endpoint — pin the
    base URL and env var so a refactor of openai_compat can't silently detach
    the quality gate's provider."""
    g = OAI_PROVIDERS["gemini"]
    assert g.api_key_env == "GEMINI_API_KEY"
    assert "generativelanguage.googleapis.com" in g.base_url


# --- Anthropic (different wire protocol) ----------------------------------------

def test_anthropic_maps_protocol_correctly(monkeypatch, fake_response):
    """Opus is the parity target — if its client mis-maps the protocol, the
    baseline arm is broken. Pins the three translation points: system messages
    lifted to the 'system' param (Messages API rejects system role in messages),
    multi-block content joined, and usage.input/output_tokens mapped to the
    uniform in/out fields."""
    import backend.providers.anthropic as an
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    captured = _fake_post(monkeypatch, an, fake_response(200, {
        "content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}],
        "usage": {"input_tokens": 20, "output_tokens": 5},
    }))

    r = registry.chat("anthropic:claude-opus-4-8",
                      [{"role": "system", "content": "be brief"},
                       {"role": "user", "content": "hi"}])

    assert captured["json"]["system"] == "be brief"
    assert all(m["role"] != "system" for m in captured["json"]["messages"])
    assert (r.text, r.tokens_in, r.tokens_out) == ("Hello world", 20, 5)


def test_anthropic_missing_usage_invalidates(monkeypatch, fake_response):
    """Same no-usage-no-result rule on the Anthropic path — both wire protocols
    must enforce it, or baseline-arm numbers could be fabricated while Ember-arm
    numbers are exact (an unfair comparison in OUR favor — the worst kind)."""
    import backend.providers.anthropic as an
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _fake_post(monkeypatch, an, fake_response(200, {"content": [{"type": "text", "text": "x"}]}))

    with pytest.raises(MissingUsageError):
        registry.chat("anthropic:claude-opus-4-8", [{"role": "user", "content": "hi"}])
