"""P2 owns — spec 04, task P2-M4. THE product entry point.
route(query) -> {"answer": str, "tier_first": str, "tier_final": str,
                 "escalations": [...], "calls": [impact-record, ...],
                 "totals": {"gco2", "cost_usd", "wh", "latency_ms"}}
Invariants: one rung per hop, <=2 hops, Opus accepted unjudged, totals == sum(calls),
EVERY call (classifier/judge/failed attempts) in calls[] — D4, nothing hidden.

Verification is a hybrid by tier (D19): trivial -> check_confidence (no second
call, ChatResult.confidence from provider logprobs); moderate -> verify (independent
judge, Gemini); hard -> skip entirely. A trivial-tier pass contributes exactly one
call to calls[]; only a moderate check or a trivial-tier escalation adds a second."""


def route(query: str) -> dict:
    raise NotImplementedError("P2-M4 — see specs/04-router.md")
