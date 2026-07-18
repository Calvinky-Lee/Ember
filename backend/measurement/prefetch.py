"""Snapshot pre-fetch (task P1-M4, spec 03 edge cases).

Run this ONCE before a judging/benchmark session while the network is up: it hits
every carbon zone (all CARBON_ZONES + the BASELINE_ZONE arm A uses) so that
carbon.get_intensity writes a last-good disk snapshot for each. After this, the
whole demo can run with Wi-Fi off and every intensity resolves at worst to
`snapshot` — never the coarse static `fallback` (KR4.1, D18 offline-first).

    uv run python -m backend.measurement.prefetch
"""
from rich.console import Console
from rich.table import Table

from backend import config
from backend.measurement import carbon

console = Console()


def prefetch(zones: list[str] | None = None) -> list[dict]:
    """Fetch each zone once; carbon.get_intensity snapshots live successes to disk.
    A zone that errors is reported but does not stop the others."""
    targets = zones or list(dict.fromkeys([*config.CARBON_ZONES, config.BASELINE_ZONE]))
    results = []
    for zone in targets:
        try:
            results.append(carbon.get_intensity(zone))
        except Exception as e:  # noqa: BLE001 — report and continue, never abort the sweep
            results.append({"zone": zone, "gco2_per_kwh": None,
                            "label": "error", "error": str(e)})
    return results


def main() -> int:
    if not config.ELECTRICITYMAPS_TOKEN:
        console.print("[yellow]No ELECTRICITYMAPS_TOKEN — zones will resolve via "
                      "snapshot/fallback, not live. Snapshots won't refresh.[/]")
    results = prefetch()
    t = Table(title="carbon snapshot pre-fetch", show_lines=False)
    for col in ("zone", "gCO2/kWh", "label"):
        t.add_column(col)
    live = 0
    for r in results:
        val = f"{r['gco2_per_kwh']:.0f}" if r.get("gco2_per_kwh") is not None else "[red]—[/]"
        label = r["label"]
        if label == "live":
            live += 1
            label = f"[green]{label}[/]"
        elif label in ("error", "fallback"):
            label = f"[yellow]{label}[/]"
        t.add_row(r["zone"], val, label)
    console.print(t)
    console.print(f"[dim]{live}/{len(results)} zones refreshed live; "
                  f"snapshot written to {carbon.SNAPSHOT_FILE}[/]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
