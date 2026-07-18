"""Single entry point: chat('provider:model', messages) → ChatResult."""
from .anthropic import AnthropicProvider
from .base import ChatResult, ProviderError
from .openai_compat import PROVIDERS as _OPENAI_COMPAT

PROVIDERS = {**_OPENAI_COMPAT, "anthropic": AnthropicProvider()}


def chat(model_key: str, messages: list[dict], **kw) -> ChatResult:
    provider_name, _, model = model_key.partition(":")
    if not model or provider_name not in PROVIDERS:
        raise ProviderError(
            f"Unknown model key {model_key!r} — expected one of "
            f"{sorted(PROVIDERS)} as 'provider:model'"
        )
    return PROVIDERS[provider_name].chat(messages, model, **kw)
