"""Precompute compact per-ticker JSON for the client app, plus screener.json.

Per ticker: {"name", "rows": [...annual...], "quarters": [...], "ttm": {...}}
Screener: composite quality score (average percentile across six factors,
direction-aware) over the whole universe.

Failures are logged and skipped — one bad ticker never fails the build.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from fundamentals import edgar  # noqa: E402
from fundamentals.metrics import compute_ratios, ttm_summary  # noqa: E402

KEEP = [
    "fiscal_year", "revenue", "cost_of_revenue", "operating_income",
    "net_income", "rnd_expense", "free_cash_flow",
    "gross_margin", "operating_margin", "net_margin", "fcf_margin",
    "rnd_intensity", "roe", "roa", "equity_multiplier", "asset_turnover",
    "current_ratio", "quick_ratio", "debt_to_equity", "interest_coverage",
    "revenue_growth", "net_income_growth", "eps_diluted",
]
SCORE_FACTORS = {  # metric -> higher_is_better
    "operating_margin": True, "fcf_margin": True, "roe": True,
    "revenue_growth": True, "debt_to_equity": False, "current_ratio": True,
}


def read_universe(path="universe.txt") -> list[str]:
    tickers = []
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tickers.extend(line.split())
    seen, out = set(), []
    for t in tickers:
        t = t.upper()
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def main() -> None:
    names = {}
    tick_file = pathlib.Path("output/tickers.json")
    if tick_file.exists():
        tick_data = json.loads(tick_file.read_text())
        names = {k: v.get("name", k) for k, v in tick_data.items()}
        for k, v in tick_data.items():
            edgar.TICKER_CIK.setdefault(k, int(v["cik"]))

    out_dir = pathlib.Path("output/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    built, failed, screener = [], [], []
    for t in read_universe():
        try:
            facts = edgar.fetch_companyfacts(t, cache_dir="data")
            df = compute_ratios(edgar.normalize(facts, t))
            df = df.tail(8)[[c for c in KEEP if c in df.columns]]
            rows = json.loads(df.to_json(orient="records"))  # NaN -> null

            quarters, ttm = [], None
            try:
                qdf = edgar.normalize_quarterly(facts)
                if not qdf.empty:
                    ttm = ttm_summary(qdf, edgar.latest_instants(facts))
                    qdf = qdf.tail(12).reset_index(names="end")
                    qdf["end"] = qdf["end"].dt.strftime("%Y-%m-%d")
                    quarters = json.loads(qdf.to_json(orient="records"))
            except Exception as e:  # noqa: BLE001
                print(f"  quarterly {t}: {e}")

            (out_dir / f"{t}.json").write_text(json.dumps(
                {"name": names.get(t, t), "rows": rows,
                 "quarters": quarters, "ttm": ttm}, separators=(",", ":")))
            built.append(t)

            if rows:
                last = rows[-1]
                screener.append({"t": t, "name": names.get(t, t),
                    "fy": last.get("fiscal_year"),
                    "revenue": last.get("revenue"),
                    **{k: last.get(k) for k in SCORE_FACTORS}})
        except Exception as e:  # noqa: BLE001
            failed.append(f"{t}: {e}")

    for factor, hib in SCORE_FACTORS.items():
        vals = sorted(r[factor] for r in screener if r.get(factor) is not None)
        n = len(vals)
        for r in screener:
            v = r.get(factor)
            if v is None or n < 2:
                r[f"_{factor}_pct"] = None
                continue
            rank = sum(1 for x in vals if x <= v) / n
            r[f"_{factor}_pct"] = rank if hib else 1 - rank
    for r in screener:
        pcts = [r.pop(f"_{f}_pct") for f in SCORE_FACTORS]
        pcts = [p for p in pcts if p is not None]
        r["score"] = round(100 * sum(pcts) / len(pcts)) if pcts else None

    pathlib.Path("output/screener.json").write_text(
        json.dumps(screener, separators=(",", ":")))
    pathlib.Path("output/universe.json").write_text(json.dumps(built))
    print(f"Built {len(built)} tickers; {len(failed)} failed; screener rows: {len(screener)}")
    for f in failed:
        print("  SKIP", f)


if __name__ == "__main__":
    main()
