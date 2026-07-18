# 02 — Providers (`backend/providers/`) — ✅ built

Uniform client layer over every model vendor. One contract, three wire protocols.

## Files & contracts

### `base.py`
```python
@dataclass
class ChatResult:
    text: str
    tokens_in: int      # provider usage field — EXACT, never a tokenizer guess
    tokens_out: int
    latency_ms: float
    model_key: str      # "provider:model" — the key into factor/price tables

class ProviderError(Exception): ...
class MissingUsageError(ProviderError): ...   # response without usage = invalid result
```

### `openai_compat.py`
`OpenAICompatProvider(name, base_url, api_key_env)` — one class covers every vendor
speaking the OpenAI chat-completions protocol:
- `groq` → `https://api.groq.com/openai/v1` (`GROQ_API_KEY`)
- `openai` → `https://api.openai.com/v1` (`OPENAI_API_KEY`)
- `gemini` → `https://generativelanguage.googleapis.com/v1beta/openai` (`GEMINI_API_KEY`)

Non-streaming always (usage field guaranteed). Missing key → `ProviderError` with a
message that says where to get one.

### `anthropic.py`
`AnthropicProvider` — Messages API (`/v1/messages`, `x-api-key`,
`anthropic-version: 2023-06-01`). System messages lifted into the `system` param;
`usage.input_tokens/output_tokens` mapped to the uniform contract.

### `registry.py`
Single entry point: `registry.chat("provider:model", messages, **kw) → ChatResult`.
Unknown provider/model-key → `ProviderError` listing valid providers.

## Model ladder (config-driven, see `.env.example`)

| Tier | Default | Why |
|---|---|---|
| trivial | `groq:llama-3.1-8b-instant` | open weights, known 8B params, ~free |
| moderate | `groq:llama-3.3-70b-versatile` | open weights, known 70B params |
| hard | `anthropic:claude-opus-4-8` | **latest Opus — the parity target and baseline arm** |
| judge | `gemini:gemini-2.5-flash` | independent family, no self-grading bias |

Fallback if no Anthropic key: `groq:moonshotai/kimi-k2-instruct` (1T-param open MoE).

## Edge cases

- **429 rate limit** → caller-side bounded concurrency (`MAX_CONCURRENCY`) +
  exponential backoff in the harness (spec 05). Provider layer surfaces the error.
- **Timeout** (default 120 s) → `ProviderError`; harness marks the query failed and
  still counts the attempt's cost/energy.
- **Missing usage field** → `MissingUsageError`; result is invalid, never estimated.
- **Sponsor-gated Gemini models** → if the sponsor key unlocks a different model,
  it's a one-line `JUDGE_MODEL` change; verify on key arrival.

## Adding a provider

OpenAI-compatible: one line in `openai_compat.PROVIDERS`. Different protocol: new
file implementing `.chat(messages, model, **kw) → ChatResult`, register in
`registry.PROVIDERS`, add factor + price rows (spec 03) — the tables error loudly
on unknown keys, so you cannot forget.

## Acceptance criteria

- `registry.chat` returns a `ChatResult` with nonzero token counts for each
  configured provider when its key is present.
- Missing-key error names the env var and the signup URL.
