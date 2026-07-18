"""`ember race` — the demo centerpiece (spec 07, P4-M1/M2). Textual TUI with a
--plain Rich fallback; both render the same RaceState (backend.tui.state) so
swapping the synthetic dev feed for the real store touches nothing here."""
from __future__ import annotations

import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Log, ProgressBar, Static

from backend.tui.state import RaceState

TICK_HZ = 30  # display lerp frame rate
POLL_S = 0.75  # how often we ask the event source for new events
REPLAY_STEP_S = 1.0 / 15  # replay reveal pace, matches state.REPLAY_EVENTS_PER_S


def _fmt(state: RaceState) -> tuple[str, str, str]:
    """Shared render strings so Textual and --plain never drift."""
    a_co2, b_co2 = state.disp_gco2["a"], state.disp_gco2["b"]
    a_cost, b_cost = state.disp_cost["a"], state.disp_cost["b"]
    esc = state.escalation_rate
    esc_s = f"{esc*100:.0f}%" if esc is not None else "—"
    prog = state.progress_fraction
    prog_s = f"{prog*100:.0f}%" if prog is not None else "?"
    co2_line = f"baseline {a_co2:8.4f} gCO2 (est)   ember {b_co2:8.4f} gCO2 (est)"
    cost_line = f"baseline ${a_cost:8.4f} (exact)   ember ${b_cost:8.4f} (exact)"
    meta_line = f"progress {prog_s} · escalation {esc_s} · {'REPLAY' if state.is_replay else 'LIVE'}"
    return co2_line, cost_line, meta_line


class CounterPair(Static):
    value_a: reactive[float] = reactive(0.0)
    value_b: reactive[float] = reactive(0.0)

    def __init__(self, label: str, unit: str, fmt: str, **kw):
        super().__init__(**kw)
        self.label = label
        self.unit = unit
        self.fmt = fmt

    def render(self) -> Text:
        t = Text()
        t.append(f"{self.label}\n", style="bold")
        t.append(f"  baseline  {self.fmt.format(self.value_a)} {self.unit}\n", style="dim")
        t.append(f"  ember     {self.fmt.format(self.value_b)} {self.unit}", style="bold orange3")
        return t


class EscalationChip(Static):
    rate: reactive[float | None] = reactive(None)

    def render(self) -> Text:
        if self.rate is None:
            return Text("escalation —", style="dim")
        pct = self.rate * 100
        style = "green" if 10 <= pct <= 30 else "yellow"
        return Text(f"escalation {pct:.0f}%", style=style)


class ReplayBanner(Static):
    active: reactive[bool] = reactive(False)

    def render(self) -> Text:
        return Text(" REPLAY — offline/finished run, re-showing recorded events ",
                    style="bold black on yellow") if self.active else Text("")


class RaceApp(App):
    CSS = """
    Screen { align: center middle; }
    #body { width: 90%; }
    CounterPair { border: round $primary; padding: 1 2; margin-bottom: 1; }
    EscalationChip { margin-bottom: 1; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, state: RaceState):
        super().__init__()
        self.state_ = state

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            yield ReplayBanner()
            with Horizontal():
                yield CounterPair("CO2", "gCO2 (est)", "{:.4f}", id="co2")
                yield CounterPair("Cost", "USD (exact)", "${:.4f}", id="cost")
            yield EscalationChip()
            yield ProgressBar(total=100, show_eta=False)
            yield Log(id="ticker", max_lines=200)
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(POLL_S, self._poll)
        self.set_interval(1 / TICK_HZ, self._tick)
        self.set_interval(REPLAY_STEP_S, self._replay_step)

    def _poll(self) -> None:
        before = len(self.state_.recent_events)
        self.state_.poll()
        new_count = len(self.state_.recent_events) - before
        if new_count > 0:
            self._log_new_events(new_count)
        self.query_one(ReplayBanner).active = self.state_.is_replay

    def _replay_step(self) -> None:
        before = len(self.state_.recent_events)
        self.state_.replay_step()
        if len(self.state_.recent_events) != before or self.state_.replay_index == 1:
            self._log_new_events(1)

    def _log_new_events(self, n: int) -> None:
        log = self.query_one("#ticker", Log)
        for ev in list(self.state_.recent_events)[-n:]:
            tier = ev.get("tier") or "-"
            mark = "-" if ev["correct"] is None else ("v" if ev["correct"] else "x")
            log.write_line(
                f"{ev['task_id']:>10} · {ev['arm']} · {ev['role']:<10} · {tier:<8} · "
                f"{ev['gco2']:.5f} gCO2 · {mark}"
            )

    def _tick(self) -> None:
        self.state_.tick(1 / TICK_HZ)
        co2 = self.query_one("#co2", CounterPair)
        co2.value_a, co2.value_b = self.state_.disp_gco2["a"], self.state_.disp_gco2["b"]
        cost = self.query_one("#cost", CounterPair)
        cost.value_a, cost.value_b = self.state_.disp_cost["a"], self.state_.disp_cost["b"]
        self.query_one(EscalationChip).rate = self.state_.escalation_rate
        prog = self.state_.progress_fraction
        self.query_one(ProgressBar).update(progress=(prog or 0) * 100)


def run_plain(state: RaceState) -> None:
    """--plain fallback: same RaceState, Rich Live instead of Textual widgets."""
    console = Console()

    def render() -> Group:
        co2_line, cost_line, meta_line = _fmt(state)
        events = Table(box=None, show_header=False)
        for ev in list(state.recent_events)[-15:]:
            tier = ev.get("tier") or "-"
            mark = "-" if ev["correct"] is None else ("v" if ev["correct"] else "x")
            events.add_row(f"{ev['task_id']}", ev["arm"], ev["role"], tier,
                           f"{ev['gco2']:.5f}", mark)
        banner = "[bold black on yellow] REPLAY [/]" if state.is_replay else ""
        return Group(
            Panel(f"{co2_line}\n{cost_line}\n{meta_line} {banner}", title="ember race"),
            events,
        )

    last_tick = time.monotonic()
    with Live(render(), console=console, refresh_per_second=TICK_HZ, screen=False) as live:
        try:
            while True:
                now = time.monotonic()
                dt = now - last_tick
                last_tick = now
                state.poll()
                state.replay_step()
                state.tick(dt)
                live.update(render())
                time.sleep(1 / TICK_HZ)
        except KeyboardInterrupt:
            pass


def run(state: RaceState, plain: bool = False) -> None:
    if plain:
        run_plain(state)
    else:
        RaceApp(state).run()
