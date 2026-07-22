"""Command-line entry point.

Usage:
    python -m fundamentals.cli --subject INTC --peers AMD NVDA TSM
"""
from __future__ import annotations

import argparse

import pandas as pd

from . import edgar, peers, report
from .metrics import compute_ratios


def main() -> None:
    ap = argparse.ArgumentParser(description="SEC fundamentals pipeline")
    ap.add_argument("--subject", default="INTC")
    ap.add_argument("--peers", nargs="+", default=["AMD", "NVDA", "TSM"])
    ap.add_argument("--out", default="output/dashboard.html")
    ap.add_argument("--cache-dir", default="data")
    ap.add_argument("--no-prices", action="store_true",
                    help="Skip Stooq price fetch / valuation multiples")
    ap.add_argument("--force", action="store_true", help="Refetch EDGAR data")
    args = ap.parse_args()

    tickers = [args.subject] + args.peers
    frames = []
    for t in tickers:
        print(f"Loading {t} from SEC EDGAR...")
        frames.append(edgar.load_ticker(t, cache_dir=args.cache_dir, force=args.force))
    ratios = compute_ratios(pd.concat(frames, ignore_index=True))
    # Keep the last 5 common fiscal years for clean charts
    last_fy = int(ratios.groupby("ticker")["fiscal_year"].max().min())
    ratios = ratios[ratios["fiscal_year"].between(last_fy - 4, last_fy)]

    table = peers.peer_table(ratios, fiscal_year=last_fy)
    if not args.no_prices:
        print("Fetching prices from Stooq...")
        table = peers.add_valuation(table, {t: peers.latest_price(t) for t in tickers})
    ranks = peers.rank_vs_peers(table, args.subject)

    out = report.build_dashboard(ratios, table, ranks, args.subject, args.out)
    ratios.to_csv("output/ratios.csv", index=False)
    print(f"Dashboard: {out}\nRatios CSV: output/ratios.csv")


if __name__ == "__main__":
    main()
