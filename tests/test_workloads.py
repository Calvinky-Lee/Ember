"""Workload integrity — the benchmark's input data IS part of the methodology
(spec 05 D13: 'provenance stated'). These tests validate the actual shipped
default.json, plus the loader's strictness on malformed files."""
import json

import pytest

from backend import config
from backend.benchmark import workloads


def test_shipped_workload_matches_spec_mix():
    """Spec 05 fixes the category mix (50 trivial / 40 math / 40 reasoning /
    20 code). A skewed mix silently changes the headline: fewer trivial tasks
    understates savings, fewer hard tasks overstates them."""
    tasks = workloads.load("default")
    counts = {}
    for t in tasks:
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    assert counts == {"trivial": 50, "math": 40, "reasoning": 40, "code": 20}


def test_shipped_workload_validates_and_ids_unique():
    """load() runs full validation — this test failing means someone hand-edited
    default.json into an invalid state (the resume key is task id, so a duplicate
    id would silently merge two tasks' results)."""
    tasks = workloads.load("default")
    assert len({t["id"] for t in tasks}) == len(tasks) == 150


def test_math_tasks_carry_gsm8k_provenance():
    """D13: judges may ask 'where did the test set come from.' The math answers
    must be parseable numbers (they came from GSM8K's '#### N' terminators) —
    a NaN here means the extraction broke and the oracle would fail everything."""
    for t in workloads.load("default"):
        if t["category"] == "math":
            float(t["oracle"]["answer"])  # raises if extraction broke


def test_limit_slices_for_dry_runs():
    """`--limit 10` is the dry-run path (spec 05 tuning protocol) — it must
    slice deterministically, not sample, so repeated dry runs are comparable."""
    assert [t["id"] for t in workloads.load("default", limit=3)] \
        == [t["id"] for t in workloads.load("default")][:3]


def test_loader_rejects_malformed_tasks(tmp_path, monkeypatch):
    """A malformed task found at load time costs nothing; found mid-benchmark it
    wastes paid Opus calls. Each rejection path must actually fire."""
    monkeypatch.setattr(config, "DATA", tmp_path)
    wl_dir = tmp_path / "workloads"
    wl_dir.mkdir()

    cases = [
        [{"id": "a", "category": "trivial", "prompt": "p", "oracle": {"type": "string_match", "answer": "x"}},
         {"id": "a", "category": "trivial", "prompt": "p", "oracle": {"type": "string_match", "answer": "x"}}],  # dup id
        [{"id": "a", "category": "nope", "prompt": "p", "oracle": {"type": "string_match", "answer": "x"}}],      # bad category
        [{"id": "a", "category": "math", "prompt": "p", "oracle": {"type": "telepathy"}}],                          # bad oracle
        [{"id": "a", "category": "reasoning", "prompt": "p", "oracle": {"type": "judge"}}],                         # judge w/o reference
        [{"id": "a", "category": "code", "prompt": "p", "oracle": {"type": "unit_test"}}],                          # unit_test w/o tests
    ]
    for tasks in cases:
        (wl_dir / "bad.json").write_text(json.dumps({"tasks": tasks}))
        with pytest.raises(workloads.WorkloadError):
            workloads.load("bad")
