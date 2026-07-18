"""OpenAI-compatible chat completions over httpx. Covers Groq and OpenAI —
both speak the same wire protocol, only base URL and key differ.
Non-streaming so the usage field is always present (spec §5)."""
import os
import time

import httpx

from .base import ChatResult, MissingUsageError, ProviderError


class OpenAICompatProvider:
    def __init__(self, name: str, base_url: str, api_key_env: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env

    def _key(self) -> str:
        key = os.getenv(self.api_key_env, "")
        if not key:
            raise ProviderError(
                f"{self.api_key_env} is not set — add it to .env "
                f"(Groq keys are free at console.groq.com/keys)"
            )
        return key

    def chat(self, messages: list[dict], model: str, *, max_tokens: int = 1024,
             temperature: float = 0.2, timeout_s: float = 120.0) -> ChatResult:
        t0 = time.monotonic()
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key()}"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            },
            timeout=timeout_s,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        if resp.status_code != 200:
            raise ProviderError(f"{self.name} HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        usage = body.get("usage")
        if not usage or "prompt_tokens" not in usage or "completion_tokens" not in usage:
            raise MissingUsageError(f"{self.name} response missing usage field")
        return ChatResult(
            text=body["choices"][0]["message"]["content"],
            tokens_in=usage["prompt_tokens"],
            tokens_out=usage["completion_tokens"],
            latency_ms=latency_ms,
            model_key=f"{self.name}:{model}",
        )


PROVIDERS = {
    "groq": OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openai": OpenAICompatProvider("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    # Google exposes an OpenAI-compatible endpoint for Gemini
    "gemini": OpenAICompatProvider(
        "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"
    ),
}


def resolve(model_key: str) -> tuple[OpenAICompatProvider, str]:
    """'groq:llama-3.1-8b-instant' → (provider, 'llama-3.1-8b-instant')."""
    provider_name, _, model = model_key.partition(":")
    if not model or provider_name not in PROVIDERS:
        raise ProviderError(
            f"Unknown model key {model_key!r} — expected 'groq:<model>' or 'openai:<model>'"
        )
    return PROVIDERS[provider_name], model


def chat(model_key: str, messages: list[dict], **kw) -> ChatResult:
    provider, model = resolve(model_key)
    return provider.chat(messages, model, **kw)
