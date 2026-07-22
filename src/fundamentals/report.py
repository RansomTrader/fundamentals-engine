"""Self-contained HTML dashboard generation.

Charts are rendered with matplotlib and embedded as base64 PNGs so the
output is a single file you can email, host on GitHub Pages, or open
locally with no dependencies.
"""
from __future__ import annotations

import base64
import io
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metrics import PERCENT_RATIOS

INK = "#16212B"
PAPER = "#F7F6F2"
ACCENT = "#0B5FA5"   # silicon blue
PEER = "#9AA7B1"
GOOD = "#2E7D5B"
BAD = "#B54834"

plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "axes.edgecolor": "#D8D4CC", "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "text.color": INK,
    "font.family": "DejaVu Sans", "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#E7E3DB", "grid.linewidth": 0.8,
})


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=144, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _fmt(val, pct: bool) -> str:
    if pd.isna(val):
        return "—"
    if pct:
        return f"{val * 100:.1f}%"
    if abs(val) >= 1e9:
        return f"${val / 1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"${val / 1e6:.0f}M"
    return f"{val:.2f}"


def trend_chart(ratios: pd.DataFrame, subject: str, metric: str, title: str) -> str:
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    pct = metric in PERCENT_RATIOS
    for tkr, grp in ratios.groupby("ticker"):
        grp = grp.sort_values("fiscal_year")
        vals = grp[metric] * (100 if pct else 1)
        is_subject = tkr == subject
        ax.plot(
            grp["fiscal_year"], vals,
            color=ACCENT if is_subject else PEER,
            linewidth=2.6 if is_subject else 1.2,
            marker="o" if is_subject else None, markersize=4,
            label=tkr, zorder=3 if is_subject else 2,
        )
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    if pct:
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.legend(fontsize=7, frameon=False, ncols=4)
    ax.set_xticks(sorted(ratios["fiscal_year"].unique()))
    return _fig_to_b64(fig)


def peer_bar_chart(table: pd.DataFrame, subject: str, metric: str, title: str) -> str:
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    pct = metric in PERCENT_RATIOS
    series = (table[metric] * (100 if pct else 1)).dropna().sort_values()
    colors = [ACCENT if t == subject else PEER for t in series.index]
    ax.barh(series.index, series.values, color=colors)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    if pct:
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    return _fig_to_b64(fig)


def _kpi_cards(snap: pd.Series) -> str:
    kpis = [
        ("Revenue", "revenue", False), ("Net income", "net_income", False),
        ("Gross margin", "gross_margin", True), ("Op. margin", "operating_margin", True),
        ("FCF margin", "fcf_margin", True), ("ROE", "roe", True),
        ("Current ratio", "current_ratio", False), ("Debt / equity", "debt_to_equity", False),
    ]
    cards = ""
    for label, col, pct in kpis:
        val = snap.get(col)
        cards += (
            f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{_fmt(val, pct)}</div></div>'
        )
    return cards


def _rank_rows(rank_df: pd.DataFrame, subject: str) -> str:
    rows = ""
    for metric, r in rank_df.iterrows():
        pct = metric in PERCENT_RATIOS
        rank_n = int(str(r["rank"]).split("/")[0])
        total = int(str(r["rank"]).split("/")[1])
        cls = "good" if rank_n <= (total + 1) // 2 else "bad"
        rows += (
            f"<tr><td>{metric.replace('_', ' ')}</td>"
            f"<td class='num'>{_fmt(r[f'{subject}_value'], pct)}</td>"
            f"<td class='num'>{_fmt(r['peer_median'], pct)}</td>"
            f"<td class='num {cls}'>{r['rank']}</td></tr>"
        )
    return rows


def build_dashboard(
    ratios: pd.DataFrame,
    peer_tbl: pd.DataFrame,
    rank_df: pd.DataFrame,
    subject: str,
    out_path: str | Path,
    notes: str = "",
) -> Path:
    fy = int(peer_tbl["fiscal_year"].iloc[0])
    snap = peer_tbl.loc[subject]
    charts = {
        "rev": trend_chart(ratios, subject, "revenue_growth", "Revenue growth, YoY"),
        "gm": trend_chart(ratios, subject, "gross_margin", "Gross margin"),
        "om": trend_chart(ratios, subject, "operating_margin", "Operating margin"),
        "fcf": trend_chart(ratios, subject, "fcf_margin", "Free-cash-flow margin"),
        "roe_bar": peer_bar_chart(peer_tbl, subject, "roe", f"ROE vs peers · FY{fy}"),
        "rnd_bar": peer_bar_chart(peer_tbl, subject, "rnd_intensity", f"R&D intensity vs peers · FY{fy}"),
    }
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject} · Fundamentals vs Peers</title><style>
:root {{ --ink:{INK}; --paper:{PAPER}; --accent:{ACCENT}; --rule:#D8D4CC; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font:15px/1.55 Georgia,'Times New Roman',serif; }}
.wrap {{ max-width:1060px; margin:0 auto; padding:32px 20px 64px; }}
header {{ border-bottom:3px solid var(--ink); padding-bottom:14px; margin-bottom:26px; }}
.eyebrow {{ font:600 11px/1 'DejaVu Sans Mono',monospace; letter-spacing:.18em;
  text-transform:uppercase; color:var(--accent); }}
h1 {{ margin:8px 0 2px; font-size:34px; letter-spacing:-.01em; }}
.sub {{ color:#5A6570; font-size:14px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
  gap:1px; background:var(--rule); border:1px solid var(--rule); margin:22px 0 30px; }}
.kpi {{ background:var(--paper); padding:12px 14px; }}
.kpi-label {{ font:600 10px/1 'DejaVu Sans Mono',monospace; letter-spacing:.12em;
  text-transform:uppercase; color:#5A6570; }}
.kpi-value {{ font:600 22px/1.3 'DejaVu Sans Mono',monospace; margin-top:6px; }}
h2 {{ font-size:20px; border-top:1px solid var(--rule); padding-top:20px; margin-top:34px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.grid img {{ width:100%; height:auto; border:1px solid var(--rule); }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th {{ text-align:left; font:600 10px/1 'DejaVu Sans Mono',monospace;
  letter-spacing:.12em; text-transform:uppercase; color:#5A6570;
  border-bottom:2px solid var(--ink); padding:8px 10px; }}
td {{ border-bottom:1px solid var(--rule); padding:7px 10px; }}
td.num {{ font-family:'DejaVu Sans Mono',monospace; text-align:right; }}
.good {{ color:{GOOD}; font-weight:600; }} .bad {{ color:{BAD}; font-weight:600; }}
.notes {{ background:#EFECE5; border-left:3px solid var(--accent); padding:14px 18px;
  margin-top:26px; font-size:14px; }}
footer {{ margin-top:40px; font:11px/1.6 'DejaVu Sans Mono',monospace; color:#8A939C; }}
@media (max-width:720px) {{ .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:26px; }} }}
</style></head><body><div class="wrap">
<header>
  <div class="eyebrow">Financial statement analysis · SEC EDGAR XBRL pipeline</div>
  <h1>{subject} fundamentals vs peers</h1>
  <div class="sub">Fiscal year {fy} snapshot · peers: {", ".join(t for t in peer_tbl.index if t != subject)} · generated {date.today().isoformat()}</div>
</header>
<div class="kpis">{_kpi_cards(snap)}</div>
<h2>Trends</h2>
<div class="grid">
  <img src="data:image/png;base64,{charts['rev']}" alt="Revenue growth">
  <img src="data:image/png;base64,{charts['gm']}" alt="Gross margin">
  <img src="data:image/png;base64,{charts['om']}" alt="Operating margin">
  <img src="data:image/png;base64,{charts['fcf']}" alt="FCF margin">
</div>
<h2>Peer comparison · FY{fy}</h2>
<div class="grid">
  <img src="data:image/png;base64,{charts['roe_bar']}" alt="ROE vs peers">
  <img src="data:image/png;base64,{charts['rnd_bar']}" alt="R&D intensity vs peers">
</div>
<h2>Rank vs peer set</h2>
<table><thead><tr><th>Metric</th><th style="text-align:right">{subject}</th>
<th style="text-align:right">Peer median</th><th style="text-align:right">Rank</th></tr></thead>
<tbody>{_rank_rows(rank_df, subject)}</tbody></table>
{f'<div class="notes">{notes}</div>' if notes else ''}
<footer>Source: SEC EDGAR companyfacts (10-K, as filed). Prices: Stooq daily close where shown.
Ratios computed by this pipeline; see README for methodology. Not investment advice.</footer>
</div></body></html>"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path
