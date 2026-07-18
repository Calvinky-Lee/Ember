"""Ember CLI — the product surface (spec 07).

  ember doctor        environment/key/data health check
  ember methodology   the audit trail: factors, sources, scope (KR3.1)
  ember route "..."   one query through Ember, with its impact receipt (P2)
  ember benchmark     run the A/B harness (P3)
  ember race          live/replay TUI race view of a run (P4)
  ember report        render a run's ESG/SCI report; --html writes the artifact (P4)
"""
import argparse
import sys

import httpx
from rich.console import Console
from rich.table import Table

from backend import config

console = Console()


def cmd_doctor(_args) -> int:
    """Everything `healthz` used to report, human-readable (task P1-M3)."""
    import os

    from backend.measurement import carbon

    t = Table(title="ember doctor", show_lines=False)
    t.add_column("check")
    t.add_column("status")
    for name, env in [("groq", "GROQ_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY"),
                      ("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY"),
                      ("electricitymaps", "ELECTRICITYMAPS_TOKEN")]:
        t.add_row(f"key: {name}", "[green]present[/]" if os.getenv(env) else "[red]missing[/]")

    em = "[yellow]no token — fallback mode[/]"
    if config.ELECTRICITYMAPS_TOKEN:
        try:
            ok = httpx.get(
                "https://api.electricitymap.org/v3/carbon-intensity/latest",
                params={"zone": config.CARBON_ZONES[0]},
                headers={"auth-token": config.ELECTRICITYMAPS_TOKEN}, timeout=5.0,
            ).status_code == 200
            em = "[green]reachable[/]" if ok else "[red]unreachable[/]"
        except httpx.HTTPError:
            em = "[red]unreachable[/]"
    t.add_row("electricity maps", em)

    factors = [k for k in config.ENERGY_FACTORS if not k.startswith("_")]
    prices = [k for k in config.PRICE_TABLE if not k.startswith("_")]
    t.add_row("energy factors", f"{len(factors)} rows")
    t.add_row("price table", f"{len(prices)} rows")
    for tier, model in config.MODEL_LADDER.items():
        ok = model in config.ENERGY_FACTORS and model in config.PRICE_TABLE
        t.add_row(f"ladder: {tier}", f"{model} " + ("[green]rows ok[/]" if ok else "[red]missing rows[/]"))
    t.add_row("judge", config.JUDGE_MODEL)

    pick = carbon.greenest_zone()
    t.add_row("greenest zone now",
              f"{pick['zone']} @ {pick['gco2_per_kwh']:.0f} gCO2/kWh ({pick['label']})")
    console.print(t)
    return 0


def cmd_methodology(_args) -> int:
    """The Deloitte 30% on demand: every factor, source, and assumption (KR3.1)."""
    console.print("[bold]Impact chain[/]: tokens (exact, provider usage) × Wh/1k-token "
                  f"factors × PUE {config.PUE} → kWh [red](estimated)[/] × grid intensity "
                  "(Electricity Maps ← grid operators) → gCO₂\n")
    t = Table(title="energy factors — rendered verbatim from data/energy_factors.json")
    for col in ("model", "Wh/1k in", "Wh/1k out", "params", "source"):
        t.add_column(col)
    for key, row in config.ENERGY_FACTORS.items():
        if key.startswith("_"):
            continue
        params = str(row.get("params_b") or "?") + ("B" if row.get("params_b") else "")
        if not row.get("params_known"):
            params = f"[red]{params} (assumed)[/]"
        t.add_row(key, str(row["wh_per_1k_in"]), str(row["wh_per_1k_out"]), params, row["source"])
    console.print(t)
    console.print("\n[bold]Scope[/] — operational inference only (SCI M=0, declared); "
                  "average not marginal intensity; assumed provider regions; simulated "
                  "placement (real region selection exists on Bedrock/Azure); "
                  "closed-model params are stated assumptions.")
    console.print("[bold]Sensitivity[/] — savings are ratio-driven by the model-size gap; "
                  "±2× factor error barely moves the reduction percentage.")
    return 0


def cmd_route(args) -> int:
    from backend.router.route import route  # P2-M4

    result = route(args.query)
    console.print(result["answer"])
    tot = result["totals"]
    console.print(f"\n[dim]tier {result['tier_first']}→{result['tier_final']} · "
                  f"~{tot['gco2']:.5f} gCO2 (est) · ${tot['cost_usd']:.6f} (exact) · "
                  f"{tot['latency_ms']:.0f} ms · {len(result['calls'])} calls "
                  f"(overhead included)[/]")
    return 0


def cmd_benchmark(args) -> int:
    from backend.benchmark.harness import run

    run_id = run(workload=args.workload, k=args.k, limit=args.limit,
                 assume_yes=args.yes, resume=args.resume)
    console.print(f"run complete: {run_id} — view with `ember race {run_id}` / `ember report {run_id}`")
    return 0


def _latest_run_id() -> str | None:
    """Shared by cmd_race/cmd_report — P1's store API (spec 06), not built yet."""
    from backend.db import store

    runs = store.list_runs()
    return runs[-1]["id"] if runs else None


def cmd_race(args) -> int:
    from backend.tui import race as race_view
    from backend.tui.state import RaceState, StoreEventSource

    run_id = args.run_id
    if run_id is None:
        try:
            run_id = _latest_run_id()
        except AttributeError:
            console.print("[red]store.list_runs() isn't implemented yet (P1, spec 06).[/] "
                           "Try `uv run python -m backend.tui._dev_synthetic` for a dev preview.")
            return 1
        if run_id is None:
            console.print("[yellow]No runs found.[/] Run `ember benchmark` first, or use "
                           "`uv run python -m backend.tui._dev_synthetic` for a dev preview.")
            return 1

    state = RaceState(StoreEventSource(run_id))
    race_view.run(state, plain=args.plain)
    return 0


def cmd_report(args) -> int:
    run_id = args.run_id
    try:
        from backend.db import store
        if run_id is None:
            run_id = _latest_run_id()
        report = store.load_report(run_id) if run_id else None
    except AttributeError:
        console.print("[red]store.load_report()/list_runs() aren't implemented yet (P1, spec 06).[/]")
        return 1
    if report is None:
        console.print(f"[yellow]No report found[/] for run {run_id!r} — run `ember benchmark` first.")
        return 1

    h = report["headline"]
    acc_str = f"{h['accuracy_delta_pp']:+.1f}pp" if h.get("accuracy_delta_pp") is not None else "—"
    lat = h["latency_p50_ms"]
    lat_str = (f"p50 {lat['b']:.0f}ms vs {lat['a']:.0f}ms"
               if lat.get("a") is not None and lat.get("b") is not None else "p50 —")
    console.print(
        f"[bold]Ember report[/] — run {run_id}\n"
        f"-{h['co2_reduction_pct']:.1f}% CO2 (est.) · "
        f"{acc_str} accuracy vs Opus · "
        f"-{h['cost_reduction_pct']:.1f}% cost (exact) · {lat_str}"
    )
    t = Table(title="per-arm")
    for col in ("arm", "answers", "errors", "calls", "gCO2 (est)", "cost (exact)"):
        t.add_column(col)
    for label, d in (("baseline", report["per_arm"]["a"]), ("ember", report["per_arm"]["b"])):
        t.add_row(label, str(d["answers"]), str(d["errors"]), str(d["calls"]),
                   f"{d['gco2']:.4f}", f"${d['cost_usd']:.4f}")
    console.print(t)
    esc = report["escalation"]
    console.print(f"escalation: {esc['rate']*100:.0f}% ({esc['count']} answers)")

    l1 = report.get("evaluation", {}).get("layer1", {})
    if "ci95_pp" in l1:
        console.print(f"accuracy Δ {l1['delta_pp']:+.1f}pp, 95% CI "
                       f"[{l1['ci95_pp'][0]:+.1f}, {l1['ci95_pp'][1]:+.1f}]pp "
                       f"({'parity met' if report['evaluation']['parity_met'] else 'parity NOT met'})")
    elif "skipped" in l1:
        console.print(f"[yellow]evaluation layer 1 skipped:[/] {l1['skipped']}")

    if args.html:
        from backend.report_html import render

        out_path = args.html
        with open(out_path, "w") as f:
            f.write(render(report))
        console.print(f"wrote {out_path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="ember", description="Carbon-aware AI inference orchestrator")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("methodology").set_defaults(fn=cmd_methodology)
    rp = sub.add_parser("route")
    rp.add_argument("query")
    rp.set_defaults(fn=cmd_route)
    bp = sub.add_parser("benchmark")
    bp.add_argument("--workload", default="default")
    bp.add_argument("--k", type=int, default=3)
    bp.add_argument("--limit", type=int, default=None)
    bp.add_argument("--resume", default=None, metavar="RUN_ID")
    bp.add_argument("--yes", action="store_true", help="skip the spend confirmation")
    bp.set_defaults(fn=cmd_benchmark)
    rc = sub.add_parser("race")
    rc.add_argument("run_id", nargs="?")
    rc.add_argument("--plain", action="store_true", help="Rich fallback, no Textual (broken-TTY insurance)")
    rc.set_defaults(fn=cmd_race)
    rt = sub.add_parser("report")
    rt.add_argument("run_id", nargs="?")
    rt.add_argument("--html", nargs="?", const="report.html", default=None, metavar="OUT",
                     help="write the self-contained HTML artifact (default: report.html)")
    rt.set_defaults(fn=cmd_report)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
