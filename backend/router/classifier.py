"""P2 owns — spec 04, task P2-M2.
classify(query) -> {"tier": "trivial"|"moderate"|"hard", "signals": {...},
                    "latency_ms": float, "overhead_call": ChatResult|None}
Heuristics first (<300ms); tiny-model call only in the unsure band; ties round UP."""


def classify(query: str) -> dict:
    raise NotImplementedError("P2-M2 — see specs/04-router.md")
