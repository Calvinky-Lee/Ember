"""P3 owns — specs 05 + 09, tasks P3-M3/M4 (KR1.3, KR2.x, KR3.4).
build(run_id) -> report dict per spec 05, including the spec 09 "evaluation" block
(paired delta + bootstrap CI, blind position-swapped judging, judge calibration,
per-tier breakdown, parity_met). Persist via db Report table."""


def build(run_id: str) -> dict:
    raise NotImplementedError("P3-M3/M4 — see specs/05-benchmark.md + 09-evaluation.md")
