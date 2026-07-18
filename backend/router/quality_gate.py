"""P2 owns — spec 04, task P2-M3.
Two verification paths, chosen by tier (hybrid design, D19):

check_confidence(chat_result) -> {"score": float, "pass": bool,
                                   "method": "self_confidence", "raw": ...}
Trivial tier ONLY. No second model call — score is the answering call's own
geometric-mean token probability (ChatResult.confidence, from provider logprobs).
pass = score >= config.CONFIDENCE_FLOOR. Missing/NaN confidence => fail (escalate).
If the trivial model doesn't support logprobs, caller falls back to verify().

verify(query, answer) -> {"score": float, "pass": bool, "judge_model": str,
                          "judge_impact": measure-record, "raw": str}
Moderate tier ONLY (hard is exempt, Opus is the parity target).
Judge = config.JUDGE_MODEL (Gemini, independent family); fallback tier-plus-one.
Unparseable verdict after one strict retry => fail (escalate = safe direction)."""

from backend.providers.base import ChatResult


def check_confidence(chat_result: ChatResult) -> dict:
    raise NotImplementedError("P2-M3 — see specs/04-router.md")


def verify(query: str, answer: str) -> dict:
    raise NotImplementedError("P2-M3 — see specs/04-router.md")
