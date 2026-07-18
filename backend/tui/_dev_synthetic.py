"""Dev-only entry point (P4-M1): run the race view against a fake in-memory run
so the TUI can be built/tested without waiting on P1's store or P3's harness.
Not part of the shipped `ember race` surface — see specs/tasks/P4-cli-demo.md.

    uv run python -m backend.tui._dev_synthetic [--plain] [--tasks N]
"""
import argparse

from backend.tui import race
from backend.tui.state import RaceState, SyntheticEventSource


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--plain", action="store_true")
    p.add_argument("--tasks", type=int, default=150)
    p.add_argument("--speed", type=float, default=3.0, help="events revealed per second")
    args = p.parse_args()

    source = SyntheticEventSource(n_tasks=args.tasks, events_per_second=args.speed)
    state = RaceState(source)
    race.run(state, plain=args.plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
