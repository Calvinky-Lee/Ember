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
    model_key: str       # "provider:model" — the key into factor/price tables
    confidence: float | None = None  # geometric-mean token probability, when requested

class ProviderError(Exception): ...
class MissingUsageError(ProviderError): ...   # response without usage = invalid result
```
`confidence` is `None` unless the caller requests `logprobs=True` (router spec 04
uses this only for the trivial-tier self-confidence gate) — never estimated or
backfilled, same "exact or absent" rule as token counts.

### `openai_compat.py`
`OpenAICompatProvider(name, base_url, api_key_env)` — one class covers every vendor
speaking the OpenAI chat-completions protocol:
- `groq` → `https://api.groq.com/openai/v1` (`GROQ_API_KEY`)
- `openai` → `https://api.openai.com/v1` (`OPENAI_API_KEY`)
- `gemini` → `https://generativelanguage.googleapis.com/v1beta/openai` (`GEMINI_API_KEY`)

Non-streaming always (usage field guaranteed). Missing key → `ProviderError` with a
message that says where to get one.

`chat(..., logprobs: bool = False)` — when set, requests `logprobs=True` on the
wire and reads `choices[0].logprobs.content` (a list of per-token logprob objects);
`confidence = exp(mean(token.logprob for token in content))`. If the vendor's
response has no `logprobs` field despite the request (protocol drift) →
`confidence` stays `None`, never guessed; the router's fallback (spec 04) covers
this. Anthropic's Messages API has no logprobs equivalent — not applicable, since
`AnthropicProvider` only ever serves the hard tier, which skips verification
entirely.

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

## Provider-boundary note (D19)

`MODEL_TRIVIAL` must resolve to a provider that speaks the OpenAI-compatible wire
protocol (`openai_compat.py`), because the trivial tier's verification path
(`check_confidence`, spec 04) requires `logprobs=True` support to populate
`ChatResult.confidence`. Verified empirically: Groq/OpenAI/Gemini via
`openai_compat.py` return real per-token logprobs on request; a unified
aggregator API (evaluated: Backboard.io) was tested against the same request and
silently drops `logprobs`/`top_logprobs` — its response schema has no field for
it, regardless of what the underlying vendor supports. **Do not route the trivial
tier through any aggregator that doesn't independently confirm logprobs
pass-through.** Moderate/hard/judge have no such constraint since they don't rely
on `confidence`.

## Acceptance criteria

- `registry.chat` returns a `ChatResult` with nonzero token counts for each
  configured provider when its key is present.
- Missing-key error names the env var and the signup URL.
