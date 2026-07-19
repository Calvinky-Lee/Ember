"""P2 owns — spec 04, task P2-M4. THE product entry point.
route(query) -> {"answer": str, "tier_first": str, "tier_final": str,
                 "escalations": [...], "calls": [impact-record, ...],
                 "totals": {"gco2", "cost_usd", "wh", "latency_ms"}}
Invariants: one rung per hop, <=2 hops, Opus accepted unjudged, totals == sum(calls),
EVERY call (classifier/judge/failed attempts) in calls[] — D4, nothing hidden.

Verification is a hybrid by tier (D19): trivial -> check_confidence (no second
call, ChatResult.confidence from the answer's own verbalized "CONFIDENCE: X" line
— NOT provider logprobs, Groq rejects that param outright); moderate -> verify
(independent judge, Gemini); hard -> skip entirely. A trivial-tier pass
contributes exactly one call to calls[]; only a moderate check or a trivial-tier
escalation adds a second."""
from backend import config
from backend.measurement.calculator import measure
from backend.providers import registry
from backend.router import classifier, quality_gate, selector

_TOTAL_KEYS = ("gco2", "cost_usd", "wh", "latency_ms")


def route(query: str) -> dict:
    calls: list[dict] = []

    zone = selector.pick_zone()["simulated"]["zone"]

    classification = classifier.classify(query)
    tier = classification["tier"]
    tier_first = tier

    overhead_call = classification["overhead_call"]
    if overhead_call is not None:
        classifier_impact = measure(
            overhead_call.model_key, overhead_call.tokens_in, overhead_call.tokens_out, zone
        )
        classifier_impact["latency_ms"] = overhead_call.latency_ms
        classifier_impact["role"] = "classifier"
        calls.append(classifier_impact)

    messages = [{"role": "user", "content": query}]
    trivial_messages = [
        {"role": "user", "content": query + quality_gate.TRIVIAL_CONFIDENCE_SUFFIX}
    ]
    escalations: list[dict] = []
    hops = 0
    answer_text = ""

    while True:
        prompt_messages = trivial_messages if tier == "trivial" else messages
        answer_result = registry.chat(config.MODEL_LADDER[tier], prompt_messages)

        if tier == "trivial" and answer_result.confidence is None:
            # Real usage: the provider layer never sets confidence (D19 uses
            # verbalized confidence, not logprobs) — parse it from the answer's
            # own "CONFIDENCE: X" line every time. If something upstream already
            # supplied a confidence value, trust it instead of re-parsing.
            clean_text, confidence = quality_gate.parse_verbalized_confidence(answer_result.text)
            answer_result.confidence = confidence
            answer_text = clean_text
        else:
            answer_text = answer_result.text

        answer_impact = measure(
            answer_result.model_key, answer_result.tokens_in, answer_result.tokens_out, zone
        )
        answer_impact["latency_ms"] = answer_result.latency_ms
        answer_impact["role"] = "answer"
        answer_impact["tier"] = tier
        calls.append(answer_impact)

        if tier == "hard":
            passed = True  # Opus is the parity target — accepted unjudged
            score = None
        elif tier == "trivial":
            if answer_result.confidence is None:
                # No parseable "CONFIDENCE: X" line — never silently skip
                # verification, fall back to the independent judge instead.
                verdict = quality_gate.verify(query, answer_text, zone)
                judge_impact = dict(verdict["judge_impact"])
                judge_impact["role"] = "judge"
                judge_impact["fallback"] = "unparseable_confidence"
                calls.append(judge_impact)
            else:
                verdict = quality_gate.check_confidence(answer_result)
            passed = verdict["pass"]
            score = verdict["score"]
        else:  # moderate
            verdict = quality_gate.verify(query, answer_text, zone)
            judge_impact = dict(verdict["judge_impact"])
            judge_impact["role"] = "judge"
            calls.append(judge_impact)
            passed = verdict["pass"]
            score = verdict["score"]

        next_tier = config.next_tier(tier)
        if passed or tier == "hard" or next_tier is None or hops >= 2:
            break

        escalations.append({"from": tier, "to": next_tier, "score": score})
        tier = next_tier
        hops += 1

    totals = {key: sum(c.get(key, 0.0) for c in calls) for key in _TOTAL_KEYS}

    return {
        "answer": answer_text,
        "tier_first": tier_first,
        "tier_final": tier,
        "escalations": escalations,
        "calls": calls,
        "totals": totals,
    }
