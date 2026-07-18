"""P2 owns — spec 04, task P2-M3.
verify(query, answer) -> {"score": float, "pass": bool, "judge_model": str,
                          "judge_impact": measure-record, "raw": str}
Judge = config.JUDGE_MODEL (Gemini, independent family); fallback tier-plus-one.
Unparseable verdict after one strict retry => fail (escalate = safe direction)."""


def verify(query: str, answer: str) -> dict:
    raise NotImplementedError("P2-M3 — see specs/04-router.md")
