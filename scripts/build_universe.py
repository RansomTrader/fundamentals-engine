"""Precompute compact per-ticker ratio JSON for the client app.

Reads universe.txt, pulls companyfacts via the pipeline, computes ratios,
and writes output/data/{TICKER}.json in the exact shape the SPA consumes:
{"name": ..., "rows": [{fiscal_year, <raw>, <ratios>}, ...]}

Failures are logged and skipped — one bad ticker never fails the build.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from fundamentals import edgar  # noqa: E402
from fundamentals.metrics import compute_ratios  # noqa: E402

KEEP = [
    "fiscal_year", "revenue", "net_income", "free_cash_flow",
    "gross_margin", "operating_margin", "net_margin", "fcf_margin",
    "rnd_intensity", "roe", "roa", "current_ratio", "quick_ratio",
    "debt_to_equity", "interest_coverage", "asset_turnover",
    "revenue_growth", "net_income_growth",
]


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
        names = {k: v.get("name", k) for k, v in json.loads(tick_file.read_text()).items()}
        # Also extend the pipeline's CIK map from the full SEC list
        for k, v in json.loads(tick_file.read_text()).items():
            edgar.TICKER_CIK.setdefault(k, int(v["cik"]))

    out_dir = pathlib.Path("output/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    built, failed = [], []
    for t in read_universe():
        try:
            df = compute_ratios(edgar.load_ticker(t, cache_dir="data"))
            df = df.tail(8)[[c for c in KEEP if c in df.columns]]
            rows = json.loads(df.to_json(orient="records"))  # NaN -> null
            (out_dir / f"{t}.json").write_text(
                json.dumps({"name": names.get(t, t), "rows": rows},
                           separators=(",", ":"))
            )
            built.append(t)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{t}: {e}")
    (pathlib.Path("output") / "universe.json").write_text(json.dumps(built))
    print(f"Built {len(built)} tickers; {len(failed)} failed")
    for f in failed:
        print("  SKIP", f)


if __name__ == "__main__":
    main()
