"""Electricity Maps client (spec 03): the degradation ladder
live → 60s cache → disk snapshot → static fallback, each rung labeled.

This ladder is what makes the demo un-killable by venue Wi-Fi (D18, spec 08 risk
table) — so every rung and every transition gets its own test.
"""
import json
import time

import pytest

from backend import config
from backend.measurement import carbon


def _fake_get(monkeypatch, responses):
    """Install a fake httpx.get; `responses` is a list consumed per call
    (an Exception instance is raised instead of returned). Returns call log."""
    calls = []

    def fake(url, **kw):
        calls.append(kw.get("params", {}).get("zone"))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(carbon.httpx, "get", fake)
    return calls


def test_live_fetch_labels_and_persists_snapshot(monkeypatch, fake_response):
    """Happy path: with a token and a healthy API, intensity is labeled 'live'
    AND written to the snapshot file — the snapshot rung only exists if live
    successes persist. A demo that fetched live all morning must survive the
    router dying at judging time."""
    monkeypatch.setattr(config, "ELECTRICITYMAPS_TOKEN", "tok")
    _fake_get(monkeypatch, [fake_response(200, {"carbonIntensity": 123.0, "datetime": "T"})])

    r = carbon.get_intensity("SE")
    assert (r["gco2_per_kwh"], r["label"]) == (123.0, "live")
    assert json.loads(carbon.SNAPSHOT_FILE.read_text())["SE"]["gco2_per_kwh"] == 123.0


def test_cache_hit_makes_no_second_http_call(monkeypatch, fake_response):
    """Within EM_CACHE_S, repeat lookups must not hit the API (rate-limit budget,
    spec 03). The fake has exactly ONE response — a second HTTP call would blow up
    with IndexError, so passing proves the cache short-circuited."""
    monkeypatch.setattr(config, "ELECTRICITYMAPS_TOKEN", "tok")
    calls = _fake_get(monkeypatch, [fake_response(200, {"carbonIntensity": 50.0})])

    carbon.get_intensity("FR")
    r2 = carbon.get_intensity("FR")
    assert r2["label"] == "cached" and len(calls) == 1


def test_expired_cache_refetches(monkeypatch, fake_response):
    """A stale cache entry (older than EM_CACHE_S) must trigger a fresh fetch —
    otherwise the 'live' number could be hours old while labeled fresh."""
    monkeypatch.setattr(config, "ELECTRICITYMAPS_TOKEN", "tok")
    carbon._cache["FR"] = (time.monotonic() - config.EM_CACHE_S - 1,
                           {"zone": "FR", "gco2_per_kwh": 1.0, "label": "live", "fetched_at": ""})
    _fake_get(monkeypatch, [fake_response(200, {"carbonIntensity": 60.0})])

    assert carbon.get_intensity("FR")["gco2_per_kwh"] == 60.0


def test_api_error_falls_to_snapshot(monkeypatch, fake_response):
    """Wi-Fi dies mid-demo: the last-good snapshot must serve, labeled 'snapshot'
    (never relabeled live). This is the rung that saves the judging session."""
    monkeypatch.setattr(config, "ELECTRICITYMAPS_TOKEN", "tok")
    carbon.SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    carbon.SNAPSHOT_FILE.write_text(json.dumps(
        {"PL": {"zone": "PL", "gco2_per_kwh": 500.0, "label": "live", "fetched_at": "T"}}))
    _fake_get(monkeypatch, [carbon.httpx.ConnectError("network down")])

    r = carbon.get_intensity("PL")
    assert (r["gco2_per_kwh"], r["label"]) == (500.0, "snapshot")


def test_api_error_no_snapshot_falls_to_static(monkeypatch):
    """Cold start with no network at all: static table serves, labeled 'fallback'
    — the value must match data/fallback_intensity.json exactly, because that
    file is what we cite in the methodology view."""
    monkeypatch.setattr(config, "ELECTRICITYMAPS_TOKEN", "tok")
    _fake_get(monkeypatch, [carbon.httpx.ConnectError("network down")])

    r = carbon.get_intensity("PL")
    assert (r["gco2_per_kwh"], r["label"]) == (config.FALLBACK_INTENSITY["PL"], "fallback")


def test_no_token_skips_api_entirely(monkeypatch):
    """Keyless mode (before O1 keys arrive): must go straight to fallback WITHOUT
    attempting HTTP — an unauthenticated request would burn time on a timeout for
    every query. The fake raises if called at all."""
    calls = _fake_get(monkeypatch, [])
    r = carbon.get_intensity("SE")
    assert r["label"] == "fallback" and calls == []


def test_null_intensity_from_api_degrades(monkeypatch, fake_response):
    """EM occasionally returns 200 with carbonIntensity: null for a zone (spec 03
    edge case). null × kWh would be a TypeError at measure time — it must degrade
    down the ladder instead of being trusted."""
    monkeypatch.setattr(config, "ELECTRICITYMAPS_TOKEN", "tok")
    _fake_get(monkeypatch, [fake_response(200, {"carbonIntensity": None})])
    assert carbon.get_intensity("SE")["label"] == "fallback"


def test_greenest_zone_picks_minimum():
    """The placement decision (D5) is literally min(intensity). With fallback data
    the winner must be the lowest-valued configured zone — computed from the table,
    not hardcoded, so P1 can retune values freely."""
    expected = min(config.CARBON_ZONES, key=lambda z: config.FALLBACK_INTENSITY[z])
    assert carbon.greenest_zone()["zone"] == expected


def test_greenest_zone_drops_unresolvable_zones():
    """Spec 03 edge case: a zone that can't be resolved is dropped for the cycle,
    not fatal — one bad zone in CARBON_ZONES must not kill routing."""
    assert carbon.greenest_zone(["NOT-A-ZONE", "PL"])["zone"] == "PL"


def test_all_zones_unresolvable_is_loud():
    """If NO zone resolves, that's a config error and must raise — silently
    routing with no intensity would produce gCO2 = None everywhere."""
    with pytest.raises(RuntimeError):
        carbon.greenest_zone(["NOT-A-ZONE"])
