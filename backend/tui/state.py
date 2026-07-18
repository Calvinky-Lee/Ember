"""Shared race-view logic (spec 07, P4-M1/M2). Framework-agnostic: both the
Textual app and the --plain Rich fallback render the same RaceState, and both
the synthetic dev feed and the real store poll through the same EventSource
protocol — swapping one for the other should never touch this file's callers.

Event dict shape (frozen, spec 06-storage.md):
{"seq": int, "task_id": str, "arm": "a"|"b", "role": "answer"|"classifier"|"judge",
 "tier": str|None, "gco2": float, "cost_usd": float, "wh": float,
 "correct": bool|None, "escalated_from": str|None,
 "energy_label": str, "intensity_label": str}
"""
from __future__ import annotations

import random
import time
from collections import deque
from typing import Protocol

from backend import config
from backend.measurement.calculator import measure

LERP_SPEED = 8.0  # higher = snaps faster to the committed value
REPLAY_IDLE_S = 10.0
REPLAY_EVENTS_PER_S = 15.0


class EventSource(Protocol):
    def poll(self, after_seq: int) -> list[dict]: ...
    def run_status(self) -> str: ...  # "running" | "done"
    def total_pairs(self) -> int | None: ...  # None = unknown, progress bar indeterminate


class StoreEventSource:
    """Wraps backend.db.store (P1) — written against the frozen spec-06 contract.
    Will not function correctly until P1 lands record_call/get_run_events, but
    doesn't block writing/testing this file."""

    def __init__(self, run_id: str):
        self.run_id = run_id

    def poll(self, after_seq: int) -> list[dict]:
        from backend.db import store
        return store.get_run_events(self.run_id, after_seq=after_seq)

    def run_status(self) -> str:
        from backend.db import store
        runs = {r["id"]: r for r in store.list_runs()}
        return runs.get(self.run_id, {}).get("status", "done")

    def total_pairs(self) -> int | None:
        # runs table (spec 06) has no task-count column; derive it from the
        # workload the run used, per spec 05's `workloads.load()`.
        from backend.db import store

        run = {r["id"]: r for r in store.list_runs()}.get(self.run_id)
        if not run:
            return None
        try:
            from backend.benchmark import workloads
            return len(workloads.load(run["workload"]))
        except NotImplementedError:
            return None


class SyntheticEventSource:
    """Dev-only fake run (M1): generates a full plausible run up front using the
    REAL energy/price tables (backend.measurement.calculator.measure), then
    reveals it over elapsed wall-clock time so `poll()` behaves exactly like a
    live harness would. Never shipped behind `ember race` — see _dev_synthetic.py."""

    def __init__(self, n_tasks: int = 150, events_per_second: float = 3.0, seed: int = 42):
        self._rng = random.Random(seed)
        self._events = self._generate(n_tasks)
        self._start = time.monotonic()
        self._events_per_second = events_per_second
        self._n_tasks = n_tasks

    def _generate(self, n_tasks: int) -> list[dict]:
        events: list[dict] = []
        seq = 0
        zone = config.BASELINE_ZONE
        for i in range(n_tasks):
            task_id = f"task-{i:03d}"

            # Arm A: baseline, always the hard-tier model.
            toks_in, toks_out = self._rng.randint(30, 200), self._rng.randint(20, 300)
            m = measure(config.MODEL_LADDER["hard"], toks_in, toks_out, zone)
            seq += 1
            events.append(self._event(seq, task_id, "a", "answer", "hard", m, correct=True))

            # Arm B: classifier overhead, then trivial attempt, then maybe escalate.
            seq += 1
            cm = measure(config.MODEL_LADDER["trivial"], 20, 1, zone)
            events.append(self._event(seq, task_id, "b", "classifier", None, cm, correct=None))

            tier = "trivial"
            toks_in, toks_out = self._rng.randint(20, 150), self._rng.randint(5, 80)
            am = measure(config.MODEL_LADDER[tier], toks_in, toks_out, zone)
            escalated_from = None
            confident = self._rng.random() > 0.18  # ~18% trivial escalation rate
            seq += 1
            events.append(self._event(seq, task_id, "b", "answer", tier, am,
                                       correct=confident, escalated_from=None))

            if not confident:
                escalated_from = tier
                tier = "moderate"
                toks_in, toks_out = self._rng.randint(50, 250), self._rng.randint(20, 150)
                am = measure(config.MODEL_LADDER[tier], toks_in, toks_out, zone)
                seq += 1
                jm = measure(config.JUDGE_MODEL, toks_in + 50, 10, zone)
                events.append(self._event(seq, task_id, "b", "judge", tier, jm, correct=None))
                passed = self._rng.random() > 0.15  # ~15% moderate escalation rate
                seq += 1
                events.append(self._event(seq, task_id, "b", "answer", tier, am,
                                           correct=passed, escalated_from=escalated_from))
                if not passed:
                    escalated_from = tier
                    tier = "hard"
                    toks_in, toks_out = self._rng.randint(30, 200), self._rng.randint(20, 300)
                    am = measure(config.MODEL_LADDER[tier], toks_in, toks_out, zone)
                    seq += 1
                    events.append(self._event(seq, task_id, "b", "answer", tier, am,
                                               correct=True, escalated_from=escalated_from))
        return events

    @staticmethod
    def _event(seq, task_id, arm, role, tier, m, *, correct, escalated_from=None) -> dict:
        return {
            "seq": seq, "task_id": task_id, "arm": arm, "role": role, "tier": tier,
            "gco2": m["gco2"], "cost_usd": m["cost_usd"], "wh": m["wh"],
            "correct": correct, "escalated_from": escalated_from,
            "energy_label": m["energy_label"], "intensity_label": m["intensity_label"],
        }

    def poll(self, after_seq: int) -> list[dict]:
        elapsed = time.monotonic() - self._start
        n_revealed = min(len(self._events), int(elapsed * self._events_per_second))
        return [e for e in self._events[:n_revealed] if e["seq"] > after_seq]

    def run_status(self) -> str:
        elapsed = time.monotonic() - self._start
        done = int(elapsed * self._events_per_second) >= len(self._events)
        return "done" if done else "running"

    def total_pairs(self) -> int | None:
        return self._n_tasks


class RaceState:
    """Accumulates arm totals from an EventSource and smooths them for display
    (D16), and flips to a labeled replay loop when the run goes idle/done (D18)."""

    def __init__(self, source: EventSource, total_pairs: int | None = None):
        self.source = source
        self.total_pairs = total_pairs if total_pairs is not None else source.total_pairs()
        self.all_events: list[dict] = []
        self.last_seq = 0
        self.mode = "live"  # "live" | "replay"
        self.replay_index = 0
        self.recent_events: deque[dict] = deque(maxlen=50)
        self._last_new_event_time = time.monotonic()
        self._reset_accumulators()

    def _reset_accumulators(self) -> None:
        self.raw_gco2 = {"a": 0.0, "b": 0.0}
        self.raw_cost = {"a": 0.0, "b": 0.0}
        self.disp_gco2 = {"a": 0.0, "b": 0.0}
        self.disp_cost = {"a": 0.0, "b": 0.0}
        self._tasks_seen_b: set[str] = set()
        self._tasks_escalated_b: set[str] = set()
        self.recent_events.clear()

    def _apply_event(self, ev: dict) -> None:
        self.raw_gco2[ev["arm"]] += ev["gco2"]
        self.raw_cost[ev["arm"]] += ev["cost_usd"]
        if ev["arm"] == "b" and ev["role"] == "answer":
            self._tasks_seen_b.add(ev["task_id"])
            if ev["escalated_from"]:
                self._tasks_escalated_b.add(ev["task_id"])
        self.recent_events.append(ev)

    # --- live path ---------------------------------------------------------
    def poll(self) -> None:
        if self.mode == "live":
            new = self.source.poll(self.last_seq)
            if new:
                self.last_seq = new[-1]["seq"]
                self.all_events.extend(new)
                for ev in new:
                    self._apply_event(ev)
                self._last_new_event_time = time.monotonic()
            status = self.source.run_status()
            if status == "done" and time.monotonic() - self._last_new_event_time > REPLAY_IDLE_S:
                self._enter_replay()
        # replay progression happens on its own cadence via replay_step()

    def _enter_replay(self) -> None:
        self.mode = "replay"
        self.replay_index = 0
        self._reset_accumulators()

    def replay_step(self) -> None:
        if self.mode != "replay":
            return
        if self.replay_index >= len(self.all_events):
            self.replay_index = 0
            self._reset_accumulators()
            return
        self._apply_event(self.all_events[self.replay_index])
        self.replay_index += 1

    def tick(self, dt: float) -> None:
        """Lerp displayed values toward the latest committed totals (D16)."""
        k = min(1.0, dt * LERP_SPEED)
        for arm in ("a", "b"):
            self.disp_gco2[arm] += (self.raw_gco2[arm] - self.disp_gco2[arm]) * k
            self.disp_cost[arm] += (self.raw_cost[arm] - self.disp_cost[arm]) * k

    @property
    def is_replay(self) -> bool:
        return self.mode == "replay"

    @property
    def escalation_rate(self) -> float | None:
        if not self._tasks_seen_b:
            return None
        return len(self._tasks_escalated_b) / len(self._tasks_seen_b)

    @property
    def progress_fraction(self) -> float | None:
        if not self.total_pairs:
            return None
        return min(1.0, len(self._tasks_seen_b) / self.total_pairs)
