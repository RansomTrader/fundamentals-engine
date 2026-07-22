"""Peer benchmarking and valuation multiples.

Prices come from Stooq's free daily CSV endpoint (no API key). If the
network call fails, valuation multiples are skipped gracefully and the
operating comparison still runs.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import requests

from .metrics import RATIO_COLUMNS

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"


def latest_price(ticker: str) -> float | None:
    try:
        resp = requests.get(STOOQ_URL.format(symbol=ticker.lower()), timeout=15)
        resp.raise_for_status()
        px = pd.read_csv(io.StringIO(resp.text))
        return float(px["Close"].iloc[-1])
    except Exception:
        return None


def peer_table(ratios: pd.DataFrame, fiscal_year: int | None = None) -> pd.DataFrame:
    """One row per ticker for the chosen fiscal year (default: latest common)."""
    if fiscal_year is None:
        fiscal_year = int(ratios.groupby("ticker")["fiscal_year"].max().min())
    snap = ratios[ratios["fiscal_year"] == fiscal_year].set_index("ticker")
    cols = ["fiscal_year", "revenue", "net_income", "free_cash_flow"] + RATIO_COLUMNS
    return snap[[c for c in cols if c in snap.columns]]


def add_valuation(table: pd.DataFrame, prices: dict[str, float | None]) -> pd.DataFrame:
    """Attach price-based multiples where price and per-share data exist."""
    t = table.copy()
    t["price"] = pd.Series(prices)
    t["market_cap"] = t["price"] * t["shares_outstanding"] if "shares_outstanding" in t else np.nan
    if "eps_diluted" in t:
        t["pe_ratio"] = t["price"] / t["eps_diluted"].replace(0, np.nan)
    if "market_cap" in t:
        t["ps_ratio"] = t["market_cap"] / t["revenue"].replace(0, np.nan)
        t["p_fcf"] = t["market_cap"] / t["free_cash_flow"].replace(0, np.nan)
    return t


def rank_vs_peers(table: pd.DataFrame, subject: str) -> pd.DataFrame:
    """Rank the subject against peers on each ratio (1 = best).

    Direction-aware: higher is better for margins/returns/coverage,
    lower is better for leverage and valuation multiples.
    """
    lower_is_better = {"debt_to_equity", "pe_ratio", "ps_ratio", "p_fcf"}
    rows = []
    for col in table.columns:
        if col in ("fiscal_year",) or table[col].dtype == object:
            continue
        series = table[col].dropna()
        if subject not in series.index or len(series) < 2:
            continue
        asc = col in lower_is_better
        rank = int(series.rank(ascending=asc)[subject])
        rows.append({
            "metric": col,
            f"{subject}_value": series[subject],
            "peer_median": series.drop(subject).median(),
            "rank": f"{rank}/{len(series)}",
        })
    return pd.DataFrame(rows).set_index("metric")
