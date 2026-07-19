"""P2 owns — spec 04, task P2-M3.
Two verification paths, chosen by tier (hybrid design, D19):

check_confidence(chat_result) -> {"score": float, "pass": bool,
                                   "method": "self_confidence", "raw": ...}
Trivial tier ONLY. No second model call — score is the answering call's own
self-reported confidence (ChatResult.confidence), verbalized in its own answer
text and parsed by parse_verbalized_confidence(), NOT provider logprobs (Groq
rejects the logprobs param outright on every model — confirmed, not a rare gap).
pass = score >= config.CONFIDENCE_FLOOR. Missing/NaN confidence => fail (escalate).
If the answer has no parseable confidence line, caller falls back to verify().

parse_verbalized_confidence(text) -> (clean_answer, confidence_or_None)
Strips the trailing "CONFIDENCE: X" line TRIVIAL_CONFIDENCE_SUFFIX asks the
trivial-tier model to produce, returning the user-facing answer text separately
from the parsed float. Works with any provider — no API feature required.

verify(query, answer, zone) -> {"score": float, "pass": bool, "judge_model": str,
                                "judge_impact": measure-record, "raw": str}
Moderate tier ONLY (hard is exempt, Opus is the parity target).
Judge = config.JUDGE_MODEL (Gemini, independent family); fallback tier-plus-one
(config.MODEL_LADDER["hard"] — verify() is moderate-only, so "one tier above the
answering model" is always Opus) when the judge key is unavailable.
Unparseable verdict after one strict retry => fail (escalate = safe direction)."""
import json
import math
import re

from backend import config
from backend.measurement.calculator import measure
from backend.providers import registry
from backend.providers.base import ChatResult, ProviderError

_SCORE_RE = re.compile(r'"score"\s*:\s*([0-9]*\.?[0-9]+)')

TRIVIAL_CONFIDENCE_SUFFIX = (
    "\n\nAfter your answer, on its own line, write exactly \"CONFIDENCE: X\" "
    "where X is a number from 0 to 1 for how sure you are this answer is "
    "fully correct."
)

_CONFIDENCE_LINE_RE = re.compile(r'(?im)^.*\bconfidence\s*:\s*([01](?:\.\d+)?|\.\d+).*$')


def parse_verbalized_confidence(text: str) -> tuple[str, float | None]:
    """(answer_with_the_confidence_line_stripped, confidence_or_None). Missing or
    unparseable is a normal outcome, not an error — caller treats None as fail
    (escalate/fallback), same safe direction as an unparseable judge verdict."""
    match = _CONFIDENCE_LINE_RE.search(text)
    if not match:
        return text.strip(), None
    try:
        value = float(match.group(1))
    except ValueError:
        return text.strip(), None
    clean = _CONFIDENCE_LINE_RE.sub("", text, count=1).strip()
    return clean, value

_RUBRIC_PROMPT = """You are grading an AI assistant's answer for correctness, \
completeness, and instruction-following.

Query: {query}

Answer: {answer}

Score the answer from 0.0 (fails) to 1.0 (perfect) on correctness, completeness, \
and instruction-following combined. Reply with ONLY a JSON object of the exact \
shape {{"score": 0.0}} — no other text."""

_STRICT_RETRY_SUFFIX = "\n\nReply with ONLY the JSON object, nothing else — no markdown, no explanation."


def _parse_score(text: str) -> float | None:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "score" in parsed:
            return float(parsed["score"])
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    match = _SCORE_RE.search(text)
    return float(match.group(1)) if match else None


def check_confidence(chat_result: ChatResult) -> dict:
    score = chat_result.confidence
    if score is None or math.isnan(score):
        return {"score": None, "pass": False, "method": "self_confidence", "raw": None}
    return {
        "score": score,
        "pass": score >= config.CONFIDENCE_FLOOR,
        "method": "self_confidence",
        "raw": score,
    }


def verify(query: str, answer: str, zone: str) -> dict:
    judge_model = config.JUDGE_MODEL
    prompt = [{"role": "user", "content": _RUBRIC_PROMPT.format(query=query, answer=answer)}]

    try:
        result = registry.chat(judge_model, prompt, max_tokens=64, temperature=0.0)
    except ProviderError:
        # Judge key unavailable — fall back one tier above the answering model.
        # verify() is moderate-tier-only (D19), so that tier is always "hard".
        judge_model = config.MODEL_LADDER["hard"]
        result = registry.chat(judge_model, prompt, max_tokens=64, temperature=0.0)

    impact = measure(result.model_key, result.tokens_in, result.tokens_out, zone)
    impact["latency_ms"] = result.latency_ms

    score = _parse_score(result.text)
    raw = result.text
    if score is None:
        # D4: the first (unparseable) attempt still cost tokens/energy — book it,
        # don't discard it just because the retry produced the usable verdict.
        retry_prompt = [{
            "role": "user",
            "content": _RUBRIC_PROMPT.format(query=query, answer=answer) + _STRICT_RETRY_SUFFIX,
        }]
        retry_result = registry.chat(judge_model, retry_prompt, max_tokens=64, temperature=0.0)
        retry_impact = measure(retry_result.model_key, retry_result.tokens_in, retry_result.tokens_out, zone)
        retry_impact["latency_ms"] = retry_result.latency_ms

        for key in ("tokens_in", "tokens_out", "wh", "gco2", "cost_usd", "latency_ms"):
            impact[key] += retry_impact[key]

        score = _parse_score(retry_result.text)
        raw = retry_result.text

    judge_impact = impact

    return {
        "score": score if score is not None else 0.0,
        "pass": score is not None and score >= config.QUALITY_FLOOR,
        "judge_model": judge_model,
        "judge_impact": judge_impact,
        "raw": raw,
    }
