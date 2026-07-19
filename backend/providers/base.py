"""Uniform provider interface. Every call returns exact token counts from the
provider's usage field — never a local tokenizer guess (spec D2/§4.1)."""
from dataclasses import dataclass


@dataclass
class ChatResult:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    model_key: str  # "provider:model", the key into factor/price tables
    confidence: float | None = None  # self-reported answer confidence (0-1); the
    # provider layer never populates this — router.quality_gate.parse_verbalized_
    # confidence() sets it after parsing the model's own "CONFIDENCE: X" line (D19).
    # Not provider logprobs: Groq rejects that API parameter outright.


class ProviderError(Exception):
    pass


class MissingUsageError(ProviderError):
    """Provider response had no usage field — result is invalid, never guess tokens."""
