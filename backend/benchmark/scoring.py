"""Per-task scoring oracles (spec 05, task P3-M3).

Deterministic oracles (string_match / numeric_exact / unit_test) are scored here
at harness time — no LLM opinion involved; this is spec 09's Layer 1. judge-oracle
tasks return correct=None here and are scored at evaluation time by blind pairwise
judging (spec 09 Layer 2) — running an absolute judge per answer at harness time
would double the judge spend for a weaker signal.
"""
import re
import subprocess
import sys

NUMBER_RE = re.compile(r"-?\$?\d[\d,]*\.?\d*")


def parse_final_number(text: str) -> float | None:
    """Last number in the text — GSM8K-style answers put the result at the end
    (our math prompts explicitly ask for that). Strips $ and thousands commas."""
    matches = NUMBER_RE.findall(text or "")
    if not matches:
        return None
    cleaned = matches[-1].replace("$", "").replace(",", "").rstrip(".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_code(text: str) -> str:
    """Model answers wrap code in markdown fences more often than not — take the
    first fenced block if present, else the raw text."""
    fence = re.search(r"```(?:python)?\s*\n(.*?)```", text or "", re.DOTALL)
    return fence.group(1) if fence else (text or "")


def score(task: dict, answer_text: str, *, timeout_s: float = 5.0) -> dict:
    """→ {"correct": bool|None, "score": float|None, "oracle": str}
    correct=None means 'not scorable here' (judge oracle — evaluation's job)."""
    oracle = task["oracle"]
    kind = oracle["type"]

    if kind == "numeric_exact":
        got = parse_final_number(answer_text)
        want = float(str(oracle["answer"]).replace(",", ""))
        ok = got is not None and abs(got - want) < 1e-6
        return {"correct": ok, "score": 1.0 if ok else 0.0, "oracle": kind}

    if kind == "string_match":
        ok = str(oracle["answer"]).casefold().strip() in (answer_text or "").casefold()
        return {"correct": ok, "score": 1.0 if ok else 0.0, "oracle": kind}

    if kind == "unit_test":
        src = extract_code(answer_text) + "\n\n" + "\n".join(oracle["tests"]) + "\n"
        try:
            # -I: isolated mode (no site-packages, no env vars). Workload code is
            # ours; the asserts are the oracle. A hang counts as failure via timeout.
            proc = subprocess.run([sys.executable, "-I", "-c", src],
                                  capture_output=True, timeout=timeout_s)
            ok = proc.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        return {"correct": ok, "score": 1.0 if ok else 0.0, "oracle": kind}

    if kind == "judge":
        return {"correct": None, "score": None, "oracle": kind}

    raise ValueError(f"unknown oracle type {kind!r}")
