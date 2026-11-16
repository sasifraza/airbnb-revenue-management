#!/usr/bin/env python3
"""make_dashboard.py - output/results.json -> output/dashboard.html (self-contained)."""
import json

R = json.load(open("output/results.json"))
res = R["results"]
order = ["Host rules (weekend/summer)", "Fixed $140", "Best fixed price", "DP optimal (RM)"]
H = R["horizon"]

dp = res["DP optimal (RM)"]; bf = res["Best fixed price"]
lift = dp["lift_vs_best_fixed"] * 100
lift_rules = (dp["revenue_mean"] / res["Host rules (weekend/summer)"]["revenue_mean"] - 1) * 100

# ---------- chart 1: revenue bars (one measure -> one hue) ----------
maxrev = max(v["revenue_mean"] for v in res.values())
W, HT, PAD_L, PAD_B = 680, 300, 10, 28
bar_h = 44; gap = 18
bars = []
for i, name in enumerate(order):
    v = res[name]
    y = 14 + i * (bar_h + gap)
    w = (v["revenue_mean"] / maxrev) * (W - 240)
    em = name.startswith("DP")
    bars.append(f'''<g class="bar" data-tip="{name}: ${v['revenue_mean']:,.0f} ± {2*v['revenue_se']:,.0f} (95% CI) · occupancy {v['occupancy']:.0%} · ADR ${v['adr']:.0f}">
      <rect x="{PAD_L}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" fill="var(--series-1)" opacity="{1 if em else 0.55}"/>
      <text x="{PAD_L+8}" y="{y+bar_h/2-7}" class="lbl-in">{name}</text>
      <text x="{PAD_L+8}" y="{y+bar_h/2+13}" class="lbl-in dim">occ {v['occupancy']:.0%} · ADR ${v['adr']:.0f}</text>
      <text x="{PAD_L+w+10:.1f}" y="{y+bar_h/2+5}" class="val">${v['revenue_mean']:,.0f}{'  (+'+format(lift,'.0f')+'% vs best fixed)' if em else ''}</text></g>''')
chart1 = f'<svg viewBox="0 0 {W} {len(order)*(bar_h+gap)+20}" role="img" aria-label="Annual revenue by pricing policy">{"".join(bars)}</svg>'

# ---------- chart 2: DP price paths over lead time (3 series, lines) ----------
paths = R["price_paths"]; names = list(paths.keys())[:3]
cols = ["var(--series-1)", "var(--series-2)", "var(--series-3)"]
all_p = [p for n in names for p in paths[n]]
pmin, pmax = min(all_p) - 10, max(all_p) + 10
W2, H2, L2, B2 = 680, 300, 46, 48
def sx(i): return L2 + i / (H - 1) * (W2 - L2 - 120)
def sy(v): return 12 + (1 - (v - pmin) / (pmax - pmin)) * (H2 - B2 - 12)
lines, labels, dots = [], [], []
for ci, n in enumerate(names):
    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(paths[n]))
    lines.append(f'<polyline points="{pts}" fill="none" stroke="{cols[ci]}" stroke-width="2"/>')
    labels.append((sy(paths[n][-1]), f'{cols[ci]}', n.split(" (")[0]))
gridv = "".join(f'<line x1="{L2}" x2="{W2-120}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" class="grid"/><text x="{L2-6}" y="{sy(v)+4:.1f}" class="tick" text-anchor="end">${v:.0f}</text>' for v in range(100, int(pmax), 50))
xt = "".join(f'<text x="{sx(i):.1f}" y="{H2-26}" class="tick" text-anchor="middle">{H-i}</text>' for i in range(0, H, 10))
hover_cells = []
for i in range(H):
    vals = "|".join(n.split(" (")[0] + ": $" + format(paths[n][i], ".0f") for n in names)
    hover_cells.append(f'<rect class="hovcol" x="{sx(i)-3:.1f}" y="10" width="6" height="{H2-B2-10}" data-tip="{H-i} days out · " data-vals="{vals}"/>')
hover2 = "".join(hover_cells)
# stagger end labels at least 16px apart
labels.sort()
placed = []
for yv, c, txt in labels:
    y = yv if not placed else max(yv, placed[-1] + 16)
    placed.append(y)
    pass
label_svg = ""
prev = -99
for (yv, c, txt) in labels:
    y = max(yv, prev + 16); prev = y
    label_svg += f'<circle cx="{sx(H-1)+6:.0f}" cy="{y:.0f}" r="4" fill="{c}"/><text x="{sx(H-1)+14:.0f}" y="{y+4:.0f}" class="dlab">{txt}</text>'
chart2 = f'<svg viewBox="0 0 {W2} {H2}" role="img" aria-label="Optimal price vs days to stay">{gridv}{xt}{"".join(lines)}{label_svg}{hover2}<text x="{(L2+W2-120)/2:.0f}" y="{H2-6}" class="tick" text-anchor="middle">days before stay date</text></svg>'
legend2 = "".join(f'<span class="leg"><i style="background:{cols[i]}"></i>{n}</span>' for i, n in enumerate(names))

# ---------- chart 3: seasonality of DP price (single series) ----------
mon = [m["dp_price"] for m in R["monthly"]]
mmin, mmax = min(mon) * 0.9, max(mon) * 1.05
W3, H3, L3 = 680, 200, 46
bw = (W3 - L3 - 20) / 12 - 6
mbars = "".join(
    f'<g class="bar" data-tip="Month {i+1}: avg DP price ${v:.0f} (quoted 14 days out)">'
    f'<rect x="{L3+i*(bw+6):.1f}" y="{14+(1-(v-mmin)/(mmax-mmin))*(H3-48):.1f}" width="{bw:.1f}" '
    f'height="{((v-mmin)/(mmax-mmin))*(H3-48):.1f}" rx="4" fill="var(--series-1)"/>'
    f'<text x="{L3+i*(bw+6)+bw/2:.1f}" y="{H3-18}" class="tick" text-anchor="middle">{"JFMAMJJASOND"[i]}</text></g>'
    for i, v in enumerate(mon))
chart3 = f'<svg viewBox="0 0 {W3} {H3}" role="img" aria-label="Average optimal price by month">{mbars}</svg>'

table_rows = "".join(f"<tr><td>{n}</td><td>${res[n]['revenue_mean']:,.0f}</td><td>±{2*res[n]['revenue_se']:,.0f}</td>"
                     f"<td>{res[n]['occupancy']:.0%}</td><td>${res[n]['adr']:.0f}</td>"
                     f"<td>{res[n]['lift_vs_best_fixed']*100:+.1f}%</td></tr>" for n in order)

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Airbnb Revenue Management - Results</title>
<style>
.viz-root {{ color-scheme: light;
  --surface-1:#fcfcfb; --page:#f9f9f7; --text-primary:#0b0b0b; --text-secondary:#52514e;
  --muted:#898781; --grid:#e1e0d9; --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a;
  --good:#006300; --border:rgba(11,11,11,.10); }}
@media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{ color-scheme: dark;
  --surface-1:#1a1a19; --page:#0d0d0d; --text-primary:#f0efec; --text-secondary:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
  --good:#0ca30c; --border:rgba(255,255,255,.10); }} }}
*{{box-sizing:border-box;margin:0}} body{{font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
.viz-root{{background:var(--page);color:var(--text-primary);min-height:100vh;padding:32px 20px}}
.wrap{{max-width:760px;margin:0 auto;display:grid;gap:18px}}
h1{{font-size:24px;letter-spacing:-.01em}} .sub{{color:var(--text-secondary)}}
.card{{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:20px}}
.card h2{{font-size:15px;margin-bottom:2px}} .card .note{{color:var(--text-secondary);font-size:13px;margin-bottom:12px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.tile .k{{font-size:13px;color:var(--text-secondary)}} .tile .v{{font-size:30px;font-weight:650}}
.tile .d{{font-size:13px;color:var(--good);font-weight:600}}
svg{{width:100%;height:auto;display:block}}
.lbl-in{{font:600 13px system-ui;fill:#fff}} .lbl-in.dim{{font-weight:400;opacity:.85;font-size:12px}}
.val{{font:600 13px system-ui;fill:var(--text-primary)}}
.dlab{{font:600 12px system-ui;fill:var(--text-secondary)}} .tick{{font:11px system-ui;fill:var(--muted)}}
.grid{{stroke:var(--grid);stroke-width:1}}
.leg{{display:inline-flex;align-items:center;gap:6px;margin-right:14px;font-size:13px;color:var(--text-secondary)}}
.leg i{{width:10px;height:10px;border-radius:3px;display:inline-block}}
.bar rect:hover{{opacity:1;filter:brightness(1.06)}} .hovcol{{fill:transparent}} .hovcol:hover{{fill:var(--grid);opacity:.5}}
#tip{{position:fixed;pointer-events:none;background:var(--text-primary);color:var(--page);padding:6px 10px;
  border-radius:8px;font-size:12.5px;display:none;z-index:9;max-width:320px}}
details{{margin-top:10px}} summary{{cursor:pointer;color:var(--text-secondary);font-size:13px}}
table{{border-collapse:collapse;width:100%;margin-top:8px;font-size:13px}}
td,th{{text-align:left;padding:6px 10px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums}}
.foot{{color:var(--muted);font-size:12.5px}}
code{{background:var(--surface-1);border:1px solid var(--border);border-radius:5px;padding:1px 5px;font-size:13px}}
</style></head>
<body><div class="viz-root"><div class="wrap">
<header><h1>Airbnb Revenue Management</h1>
<p class="sub">Single-listing dynamic pricing as a perishable-inventory problem — demand fitted from booking logs, prices set by dynamic programming, validated by Monte Carlo against the hidden ground-truth market.</p></header>

<div class="card tiles">
  <div class="tile"><div class="k">Revenue lift vs best fixed price</div><div class="v">+{lift:.0f}%</div><div class="d">${dp['revenue_mean']-bf['revenue_mean']:,.0f} / year</div></div>
  <div class="tile"><div class="k">vs hand-tuned host rules</div><div class="v">+{lift_rules:.0f}%</div></div>
  <div class="tile"><div class="k">Occupancy under RM</div><div class="v">{dp['occupancy']:.0%}</div><div class="d">down from 100% — by design</div></div>
  <div class="tile"><div class="k">Avg daily rate (RM)</div><div class="v">${dp['adr']:.0f}</div></div>
</div>

<div class="card"><h2>Annual revenue by pricing policy</h2>
<p class="note">{R['n_years_sim']} simulated years per policy · bars show the mean; hover for 95% CI, occupancy and rate</p>
{chart1}
<details><summary>Table view</summary><table><tr><th>Policy</th><th>Revenue</th><th>95% CI</th><th>Occupancy</th><th>ADR</th><th>vs best fixed</th></tr>{table_rows}</table></details></div>

<div class="card"><h2>The optimal price path — how RM thinks</h2>
<p class="note">Price quoted while the night is still unsold. High when time remains, falling toward the stay date as spoilage risk grows — then re-set by date strength. Hover for values.</p>
<div style="margin-bottom:8px">{legend2}</div>
{chart2}</div>

<div class="card"><h2>Seasonality the optimizer learned</h2>
<p class="note">Average optimal price (quoted 14 days out) by month — learned from logs, never told the season explicitly</p>
{chart3}</div>

<div class="card"><h2>Why this is the airline problem</h2>
<p class="note" style="margin-bottom:0">A stay-night is one unit of perishable inventory with a {H}-day booking window — exactly an airline seat. The optimal policy solves
V(t) = max<sub>p</sub> q(p,t)·p + (1−q(p,t))·V(t−1), the single-unit RM recursion. The historical host sold out
({R['history_occupancy']:.0%} occupancy) — which looks healthy and is the signature of underpricing; the optimizer deliberately trades occupancy
({dp['occupancy']:.0%}) for rate (${dp['adr']:.0f} vs ${res['Host rules (weekend/summer)']['adr']:.0f}), the core RM insight. Demand model: Poisson arrivals (Fourier seasonality × weekend × lead-time curve)
with lognormal willingness-to-pay fitted by censored maximum likelihood (σ̂ = {R['sigma_hat']:.2f}, truth 0.32).</p></div>

<p class="foot">Synthetic market, {R['n_years_sim']} Monte Carlo years per policy, runtime {R['runtime_s']}s · code: <code>bnbrm/</code> (market · model · optimize) + <code>run.py</code></p>
</div><div id="tip"></div>
<script>
const tip=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(el=>{{
  el.addEventListener('mousemove',e=>{{
    let t=el.dataset.tip; if(el.dataset.vals) t+=' '+el.dataset.vals.split('|').join(' · ');
    tip.textContent=t; tip.style.display='block';
    tip.style.left=Math.min(e.clientX+14,innerWidth-330)+'px'; tip.style.top=(e.clientY+14)+'px';}});
  el.addEventListener('mouseleave',()=>tip.style.display='none');}});
</script></div></body></html>"""
open("output/dashboard.html", "w").write(html)
print("output/dashboard.html", len(html), "bytes")
