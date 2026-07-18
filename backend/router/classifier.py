"""P2 owns — spec 04, task P2-M2.
classify(query) -> {"tier": "trivial"|"moderate"|"hard", "signals": {...},
                    "latency_ms": float, "overhead_call": ChatResult|None}
Heuristics first (<300ms); tiny-model call only in the unsure band; ties round UP."""
import re
import time

from backend import config
from backend.providers import registry

_MATH_MARKERS = re.compile(r"[+\-*/=×÷∫∑√]|\bsolve\b|\bprove\b|\bcalculate\b|\bequation\b", re.I)
_CODE_MARKERS = re.compile(r"```|\bdef \b|\bclass \b|;\s*$|\{|\}|\bfunction\b", re.I | re.M)
_REASONING_MARKERS = re.compile(
    r"\bwhy\b|\bexplain\b|\bstep by step\b|\bcompare\b|\banalyz|\bimplications?\b", re.I
)
_LONG_OUTPUT_MARKERS = re.compile(r"\bessay\b|\bdetailed\b|\blist all\b|\bcomprehensive\b", re.I)

# Heuristic score thresholds — below LOW is confidently trivial, above HIGH is
# confidently hard, the band between is the unsure zone (one cheap LLM call).
_LOW = 1
_HIGH = 3


def _heuristic_score(query: str) -> tuple[int, dict]:
    words = query.split()
    signals = {
        "word_count": len(words),
        "has_math": bool(_MATH_MARKERS.search(query)),
        "has_code": bool(_CODE_MARKERS.search(query)),
        "has_reasoning": bool(_REASONING_MARKERS.search(query)),
        "wants_long_output": bool(_LONG_OUTPUT_MARKERS.search(query)),
    }
    score = 0
    if len(words) > 40:
        score += 2
    elif len(words) > 15:
        score += 1
    score += int(signals["has_math"])
    score += 2 * int(signals["has_code"])
    score += int(signals["has_reasoning"])
    score += int(signals["wants_long_output"])
    return score, signals


def _tier_for_score(score: int) -> str | None:
    """None means 'unsure' — caller falls back to the overhead LLM call."""
    if score <= _LOW:
        return "trivial"
    if score >= _HIGH:
        return "hard"
    return None


def _parse_difficulty_digit(text: str) -> str:
    match = re.search(r"[123]", text)
    if not match:
        return "moderate"  # unparseable -> round UP, never silently trivial
    return {"1": "trivial", "2": "moderate", "3": "hard"}[match.group()]


def classify(query: str) -> dict:
    t0 = time.monotonic()
    score, signals = _heuristic_score(query)
    tier = _tier_for_score(score)
    overhead_call = None

    if tier is None:
        prompt = [{
            "role": "user",
            "content": (
                "Rate the difficulty of the following query as 1 (trivial), "
                "2 (moderate), or 3 (hard). Reply with exactly one digit, "
                f"nothing else.\n\nQuery: {query}"
            ),
        }]
        overhead_call = registry.chat(
            config.MODEL_LADDER["trivial"], prompt, max_tokens=4, temperature=0.0
        )
        tier = _parse_difficulty_digit(overhead_call.text)

    return {
        "tier": tier,
        "signals": signals,
        "latency_ms": (time.monotonic() - t0) * 1000,
        "overhead_call": overhead_call,
    }
