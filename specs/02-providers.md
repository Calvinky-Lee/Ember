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
    confidence: float | None = None  # self-reported answer confidence, when parsed

class ProviderError(Exception): ...
class MissingUsageError(ProviderError): ...   # response without usage = invalid result
```
`confidence` is always `None` coming out of the provider layer — no provider sets
it. The router (spec 04) populates it after the fact by parsing the trivial-tier
model's own verbalized `"CONFIDENCE: X"` line out of its answer text
(`quality_gate.parse_verbalized_confidence`), not from any API feature.

**This was originally designed around provider `logprobs` instead** (request
`logprobs=True`, derive confidence from token log-probabilities). Abandoned after
verifying live: Groq rejects the `logprobs` parameter outright, on every model,
with no announced timeline (confirmed via a real 400 — `"logprobs is not
supported with this model"` — and Groq's own community forum). That's a hardware/
API-level fact, not a rare gap, so there was no viable per-provider fallback that
kept Groq as the trivial-tier host. Verbalized confidence works with any
provider, no API feature required, which is why it replaced logprobs entirely
rather than being bolted on as a special case.

### `openai_compat.py`
`OpenAICompatProvider(name, base_url, api_key_env)` — one class covers every vendor
speaking the OpenAI chat-completions protocol:
- `groq` → `https://api.groq.com/openai/v1` (`GROQ_API_KEY`)
- `openai` → `https://api.openai.com/v1` (`OPENAI_API_KEY`)
- `gemini` → `https://generativelanguage.googleapis.com/v1beta/openai` (`GEMINI_API_KEY`)

Non-streaming always (usage field guaranteed). Missing key → `ProviderError` with a
message that says where to get one. No `logprobs` parameter — see the confidence
note above for why.

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

None, currently — this is a change from an earlier version of this spec. Trivial
tier's confidence signal is verbalized (parsed from the answer's own text), not a
provider API feature, so it has no wire-protocol requirement and can run on any
provider, including Groq. (History: an earlier design used `logprobs=True`
instead, which ruled out both Groq — rejects the parameter outright, confirmed
live — and any aggregator like Backboard.io, whose response schema drops
`logprobs` regardless of the underlying vendor. That constraint no longer applies
since the mechanism changed.)

Separately, Backboard.io remains a legitimate execution layer for moderate/hard/
judge (no confidence dependency there) per the standing project decision to
consolidate on Backboard wherever there's no technical blocker — see the
Backboard provider strategy note if adding `backend/providers/backboard.py`.

## Acceptance criteria

- `registry.chat` returns a `ChatResult` with nonzero token counts for each
  configured provider when its key is present.
- Missing-key error names the env var and the signup URL.
