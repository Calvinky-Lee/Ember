"""`ember report --html` (spec 07, P4-M3): a single self-contained HTML file —
inline CSS, zero external assets, opens from disk, survives airplane mode,
prints cleanly. Renders the spec-05 report dict (headline/per_arm/escalation/
sci/extrapolation/labels) plus spec-09's evaluation block, and a methodology
appendix built from the same data/energy_factors.json + price_table.json rows
`ember methodology` renders — the two views share one source, so they can't drift."""
import html

from backend import config

_CSS = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       max-width: 880px; margin: 2rem auto; padding: 0 1.5rem; line-height: 1.45;
       color: #1a1a1a; background: #fff; }
h1 { font-size: 1.6rem; margin-bottom: 0; }
h2 { font-size: 1.15rem; margin-top: 2.2rem; border-bottom: 2px solid #e0752f; padding-bottom: .3rem; }
.subtitle { color: #666; margin-top: .2rem; }
.headline { display: flex; gap: 1.2rem; flex-wrap: wrap; margin: 1.2rem 0; }
.stat { background: #faf3ee; border: 1px solid #e0752f33; border-radius: 10px;
        padding: .9rem 1.2rem; min-width: 150px; }
.stat .big { font-size: 1.6rem; font-weight: 700; color: #b1541c; }
.stat .lbl { font-size: .8rem; color: #777; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0 1.2rem; font-size: .92rem; }
th, td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #eee; }
th { color: #555; font-weight: 600; }
.label { display: inline-block; font-size: .68rem; padding: .1rem .4rem; border-radius: 4px;
         background: #eee; color: #555; margin-left: .3rem; }
.label.exact { background: #dff3e3; color: #1f7a3d; }
.label.estimated { background: #fdeecb; color: #94620a; }
.scope { font-size: .88rem; color: #444; background: #f7f7f7; border-radius: 8px; padding: .8rem 1rem; }
.parity-yes { color: #1f7a3d; font-weight: 600; }
.parity-no { color: #b3261e; font-weight: 600; }
@media print {
  body { color: #000; }
  .stat { border: 1px solid #999; background: #fff; }
  h2 { color: #000; }
}
@media (prefers-color-scheme: dark) {
  body { background: #14110f; color: #eee; }
  .stat { background: #241c16; border-color: #e0752f55; }
  th, td { border-bottom-color: #333; }
  .scope { background: #1d1a17; color: #ccc; }
}
"""


def _label(kind: str) -> str:
    return f'<span class="label {kind}">{kind}</span>'


def _headline(h: dict) -> str:
    lat_a, lat_b = h["latency_p50_ms"].get("a"), h["latency_p50_ms"].get("b")
    lat_str = (f"{lat_b:.0f}ms vs {lat_a:.0f}ms" if lat_a is not None and lat_b is not None
               else "—")
    stats = [
        (f"-{h['co2_reduction_pct']:.1f}%", "CO2 reduction (est.)"),
        (f"{h['accuracy_delta_pp']:+.1f}pp" if h.get("accuracy_delta_pp") is not None else "—",
         "accuracy delta vs Opus"),
        (f"-{h['cost_reduction_pct']:.1f}%", "cost reduction (exact)"),
        (lat_str, "latency p50 (ember vs baseline)"),
    ]
    cards = "".join(f'<div class="stat"><div class="big">{v}</div><div class="lbl">{l}</div></div>'
                     for v, l in stats)
    return f'<div class="headline">{cards}</div>'


def _per_arm_table(per_arm: dict) -> str:
    a, b = per_arm["a"], per_arm["b"]
    rows = "".join(
        f"<tr><td>{arm_label}</td><td>{d['answers']}</td><td>{d['errors']}</td>"
        f"<td>{d['calls']}</td><td>{d['gco2']:.4f}</td><td>${d['cost_usd']:.4f}</td></tr>"
        for arm_label, d in (("baseline (all-Opus)", a), ("ember (routed)", b))
    )
    return (
        "<table><thead><tr><th>arm</th><th>answers</th><th>errors</th><th>calls</th>"
        f"<th>gCO2 {_label('estimated')}</th><th>cost {_label('exact')}</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _escalation(esc: dict) -> str:
    return (
        f"<p>Ember's escalation rate: <strong>{esc['rate']*100:.0f}%</strong> "
        f"({esc['count']} of the routed answers) — healthy band 10–30%, proof the "
        "gate is doing real work, not a bug.</p>"
    )


def _layer_or_skip(layer: dict, render_fn) -> str:
    if "skipped" in layer:
        return f'<p class="scope">Skipped: {html.escape(layer["skipped"])}</p>'
    return render_fn(layer)


def _evaluation(ev: dict) -> str:
    parity_cls = "parity-yes" if ev["parity_met"] else "parity-no"
    per_tier_rows = "".join(
        f"<tr><td>{t['tier']}</td><td>{t['n']}</td><td>{t['delta_pp']:+.1f}pp</td></tr>"
        for t in ev["per_tier"]
    )
    per_tier_html = (
        f'<table><thead><tr><th>tier</th><th>n</th><th>accuracy Δ vs Opus</th></tr></thead>'
        f"<tbody>{per_tier_rows}</tbody></table>"
    ) if ev["per_tier"] else '<p class="scope">No per-tier breakdown (no paired ground-truth tasks).</p>'

    layer1_html = _layer_or_skip(ev["layer1"], lambda l1: (
        f"<p>Layer 1 (ground-truth oracles): Δ = <strong>{l1['delta_pp']:+.1f}pp</strong>, "
        f"95% CI [{l1['ci95_pp'][0]:+.1f}, {l1['ci95_pp'][1]:+.1f}]pp over {l1['n_tasks']} "
        f"tasks (K={l1['k']}). Parity criterion \"{ev['parity_criterion']}\": "
        f"<span class=\"{parity_cls}\">{'MET' if ev['parity_met'] else 'NOT MET'}</span>.</p>"
    ))
    layer2_html = _layer_or_skip(ev["layer2"], lambda l2: (
        f"<p>Layer 2 (blind pairwise judging): {l2['wins_b']} wins · {l2['ties']} ties · "
        f"{l2['losses_b']} losses for ember, {l2['position_flips']} position-flip ties"
        + (" — <strong>flip rate &gt;20%, demoted to inconclusive</strong>" if l2.get("inconclusive") else "")
        + ".</p>"
    ))
    layer3_html = _layer_or_skip(ev["layer3"], lambda l3: (
        f"<p>Layer 3 (judge calibration): agrees with ground truth "
        f"<strong>{l3['judge_agreement_pct']:.0f}%</strong> of the time "
        f"(false-pass rate {l3['judge_false_pass_pct']:.1f}%).</p>"
    ))
    return f"{layer1_html}{layer2_html}{layer3_html}{per_tier_html}"


def _sci(sci: dict) -> str:
    a, b = sci["per_query_gco2"]["a"], sci["per_query_gco2"]["b"]
    return (
        f"<p>SCI (Software Carbon Intensity), functional unit = {sci['functional_unit']}, "
        f"embodied M={sci['m']} (declared out of scope): baseline {a:.5f} gCO2/query vs "
        f"ember {b:.5f} gCO2/query.</p>"
    )


def _extrapolation(ex: dict) -> str:
    return (
        f"<p>At {ex['queries_per_day']:,} queries/day: "
        f"<strong>{ex['tonnes_co2_per_year_saved']:.1f} tonnes CO2/year saved</strong> "
        f"{_label(ex['label'])}.</p>"
    )


def _methodology() -> str:
    rows = []
    for key, row in config.ENERGY_FACTORS.items():
        if key.startswith("_"):
            continue
        params = f"{row.get('params_b') or '?'}B" if row.get("params_b") else "undisclosed"
        known = "" if row.get("params_known") else " (assumed)"
        rows.append(
            f"<tr><td>{html.escape(key)}</td><td>{row['wh_per_1k_in']}</td>"
            f"<td>{row['wh_per_1k_out']}</td><td>{params}{known}</td>"
            f"<td>{html.escape(row['source'])}</td></tr>"
        )
    table = (
        "<table><thead><tr><th>model</th><th>Wh/1k in</th><th>Wh/1k out</th>"
        f"<th>params</th><th>source</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    return (
        "<div class=\"scope\">Operational inference only (SCI M=0, declared); average "
        "not marginal grid intensity; assumed provider regions; simulated placement "
        "(real region selection exists on Bedrock/Azure); closed-model params are "
        "stated assumptions, never silently guessed. Savings are ratio-driven by the "
        "model-size gap — a ±2x factor error barely moves the reduction percentage.</div>"
        f"{table}"
    )


def render(report: dict) -> str:
    labels = report["labels"]
    body = f"""
    <h1>Ember — ESG / SCI Report</h1>
    <p class="subtitle">run <code>{html.escape(report.get('run_id', ''))}</code> ·
    energy {_label(labels['energy'])} · cost {_label(labels['cost'])} ·
    grid intensity {_label(labels['intensity_mode'])}</p>

    {_headline(report['headline'])}

    <h2>Per-arm results</h2>
    {_per_arm_table(report['per_arm'])}

    <h2>Escalation</h2>
    {_escalation(report['escalation'])}

    <h2>Evaluation vs all-Opus baseline</h2>
    {_evaluation(report['evaluation'])}

    <h2>SCI framing</h2>
    {_sci(report['sci'])}

    <h2>Extrapolation</h2>
    {_extrapolation(report['extrapolation'])}

    <h2>Methodology</h2>
    {_methodology()}
    """
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Ember report</title>"
        f"<style>{_CSS}</style></head><body>{body}</body></html>"
    )
