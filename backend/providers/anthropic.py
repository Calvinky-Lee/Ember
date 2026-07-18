"""Anthropic Messages API client — different wire protocol from the
OpenAI-compatible providers (x-api-key header, /v1/messages, usage.input_tokens).
Same uniform ChatResult contract; usage field is mandatory (spec §5)."""
import os
import time

import httpx

from .base import ChatResult, MissingUsageError, ProviderError

BASE = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"


class AnthropicProvider:
    name = "anthropic"

    def _key(self) -> str:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY is not set — add it to .env (console.anthropic.com)")
        return key

    def chat(self, messages: list[dict], model: str, *, max_tokens: int = 1024,
             temperature: float = 0.2, timeout_s: float = 120.0) -> ChatResult:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        chat_messages = [m for m in messages if m["role"] != "system"]
        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system:
            body["system"] = system

        t0 = time.monotonic()
        resp = httpx.post(
            f"{BASE}/messages",
            headers={
                "x-api-key": self._key(),
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            json=body,
            timeout=timeout_s,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        if resp.status_code != 200:
            raise ProviderError(f"anthropic HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        usage = data.get("usage")
        if not usage or "input_tokens" not in usage or "output_tokens" not in usage:
            raise MissingUsageError("anthropic response missing usage field")
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return ChatResult(
            text=text,
            tokens_in=usage["input_tokens"],
            tokens_out=usage["output_tokens"],
            latency_ms=latency_ms,
            model_key=f"anthropic:{model}",
        )
