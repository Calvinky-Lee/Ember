"""Workload loading + validation (spec 05, task P3-M1).

Validation is strict on load — a malformed task discovered mid-benchmark wastes
paid Opus calls; discovered at load time it costs nothing.
"""
import json

from backend import config

CATEGORIES = {"trivial", "math", "reasoning", "code"}
ORACLE_TYPES = {"string_match", "numeric_exact", "unit_test", "judge"}


class WorkloadError(Exception):
    pass


def load(name: str = "default", limit: int | None = None) -> list[dict]:
    path = config.DATA / "workloads" / f"{name}.json"
    if not path.exists():
        raise WorkloadError(f"No workload file at {path} — run scripts/build_workload.py")
    tasks = json.loads(path.read_text())["tasks"]

    seen = set()
    for t in tasks:
        for field in ("id", "category", "prompt", "oracle"):
            if not t.get(field):
                raise WorkloadError(f"task missing {field!r}: {t}")
        if t["id"] in seen:
            raise WorkloadError(f"duplicate task id {t['id']!r}")
        seen.add(t["id"])
        if t["category"] not in CATEGORIES:
            raise WorkloadError(f"{t['id']}: unknown category {t['category']!r}")
        oracle = t["oracle"]
        if oracle.get("type") not in ORACLE_TYPES:
            raise WorkloadError(f"{t['id']}: unknown oracle type {oracle.get('type')!r}")
        if oracle["type"] in ("string_match", "numeric_exact") and not oracle.get("answer"):
            raise WorkloadError(f"{t['id']}: {oracle['type']} oracle needs an answer")
        if oracle["type"] == "judge" and not oracle.get("reference"):
            raise WorkloadError(f"{t['id']}: judge oracle needs a reference answer")
        if oracle["type"] == "unit_test" and not oracle.get("tests"):
            raise WorkloadError(f"{t['id']}: unit_test oracle needs tests")

    return tasks[:limit] if limit else tasks
