"""Ratio and derived-metric computation on normalized annual data."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def compute_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Add margin, return, liquidity, leverage, and cash-flow ratios.

    Expects one row per (ticker, fiscal_year) with the columns produced
    by edgar.normalize(). Missing inputs yield NaN, never an exception.
    """
    d = df.copy().sort_values(["ticker", "fiscal_year"])
    for col in [
        "revenue", "cost_of_revenue", "gross_profit", "operating_income",
        "net_income", "rnd_expense", "interest_expense", "assets",
        "current_assets", "current_liabilities", "inventory", "equity",
        "total_debt_lt", "total_debt_st", "cash", "operating_cash_flow",
        "capex", "shares_outstanding", "eps_diluted",
    ]:
        if col not in d.columns:
            d[col] = np.nan

    # Fill gross profit if only revenue and COGS were filed
    d["gross_profit"] = d["gross_profit"].fillna(d["revenue"] - d["cost_of_revenue"])
    d["total_debt"] = d[["total_debt_lt", "total_debt_st"]].sum(axis=1, min_count=1)
    d["free_cash_flow"] = d["operating_cash_flow"] - d["capex"]

    # Margins
    d["gross_margin"] = _safe_div(d["gross_profit"], d["revenue"])
    d["operating_margin"] = _safe_div(d["operating_income"], d["revenue"])
    d["net_margin"] = _safe_div(d["net_income"], d["revenue"])
    d["fcf_margin"] = _safe_div(d["free_cash_flow"], d["revenue"])
    d["rnd_intensity"] = _safe_div(d["rnd_expense"], d["revenue"])

    # Returns
    d["roe"] = _safe_div(d["net_income"], d["equity"])
    d["roa"] = _safe_div(d["net_income"], d["assets"])

    # Liquidity
    d["current_ratio"] = _safe_div(d["current_assets"], d["current_liabilities"])
    d["quick_ratio"] = _safe_div(
        d["current_assets"] - d["inventory"].fillna(0), d["current_liabilities"]
    )

    # Leverage / coverage
    d["debt_to_equity"] = _safe_div(d["total_debt"], d["equity"])
    d["interest_coverage"] = _safe_div(d["operating_income"], d["interest_expense"])

    # Efficiency & growth
    d["asset_turnover"] = _safe_div(d["revenue"], d["assets"])
    d["revenue_growth"] = d.groupby("ticker")["revenue"].pct_change()
    d["net_income_growth"] = d.groupby("ticker")["net_income"].pct_change()

    return d


RATIO_COLUMNS = [
    "gross_margin", "operating_margin", "net_margin", "fcf_margin",
    "rnd_intensity", "roe", "roa", "current_ratio", "quick_ratio",
    "debt_to_equity", "interest_coverage", "asset_turnover",
    "revenue_growth", "net_income_growth",
]

PERCENT_RATIOS = {
    "gross_margin", "operating_margin", "net_margin", "fcf_margin",
    "rnd_intensity", "roe", "roa", "revenue_growth", "net_income_growth",
}
