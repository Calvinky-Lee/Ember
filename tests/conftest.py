"""Shared test fixtures.

Principles for this suite (read before adding tests):
- Every test's docstring states WHAT behavior it pins down and WHY it matters —
  usually a spec decision (D1–D18) or a failure mode from specs/05 §edge-cases.
- No network, ever: httpx is faked. No real API keys are read or needed.
- Data-VALUE tests are dynamic (they read the table), data-SHAPE tests are strict —
  so P1 can update factor/price values without breaking tests, but cannot break
  the schema or ladder consistency without hearing about it.
"""
import json

import pytest

from backend import config
from backend.measurement import carbon


class FakeResponse:
    """Minimal stand-in for httpx.Response — just what our code touches."""

    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


@pytest.fixture
def fake_response():
    return FakeResponse


@pytest.fixture(autouse=True)
def isolated_carbon(monkeypatch, tmp_path):
    """Every test gets a clean carbon module: empty in-memory cache, a throwaway
    snapshot file, and NO Electricity Maps token (tests opt in to a token).
    Without this, one test's cache/snapshot writes would leak into the next —
    exactly the kind of ordering flakiness that makes people ignore failures."""
    monkeypatch.setattr(carbon, "_cache", {})
    monkeypatch.setattr(carbon, "SNAPSHOT_FILE", tmp_path / "intensity.json")
    monkeypatch.setattr(config, "ELECTRICITYMAPS_TOKEN", "")
    yield
