"""SEC EDGAR companyfacts client.

Pulls XBRL company facts from the SEC's free JSON API, caches raw
responses to disk, and normalizes them into a tidy DataFrame of
annual (10-K) values per accounting concept.

SEC fair-access policy requires a descriptive User-Agent with contact
info. Set EDGAR_USER_AGENT or pass user_agent explicitly.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

TICKER_CIK = {
    # Hardcoded to avoid an extra lookup call; extend as needed or use
    # https://www.sec.gov/files/company_tickers.json for full coverage.
    "INTC": 50863,
    "AMD": 2488,
    "NVDA": 1045810,
    "TSM": 1046179,
    "TXN": 97476,
    "MU": 723125,
    "QCOM": 804328,
}

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Concept fallbacks: first tag found wins. Companies vary in which
# us-gaap tags they file under, so each metric lists alternatives.
CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "rnd_expense": ["ResearchAndDevelopmentExpense"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "inventory": ["InventoryNet"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "total_debt_lt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "total_debt_st": ["LongTermDebtCurrent", "DebtCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "shares_outstanding": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
}

# Balance-sheet concepts are instant (point-in-time); flows cover a duration.
INSTANT_METRICS = {
    "assets", "current_assets", "current_liabilities", "inventory",
    "equity", "total_debt_lt", "total_debt_st", "cash",
}


def fetch_companyfacts(
    ticker: str,
    cache_dir: str | Path = "data",
    user_agent: str | None = None,
    force: bool = False,
) -> dict:
    """Fetch (or load cached) companyfacts JSON for a ticker."""
    ticker = ticker.upper()
    if ticker not in TICKER_CIK:
        raise KeyError(f"Unknown ticker {ticker}; add its CIK to TICKER_CIK.")
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{ticker}_companyfacts.json"
    if cache_file.exists() and not force:
        return json.loads(cache_file.read_text())

    ua = user_agent or os.environ.get("EDGAR_USER_AGENT")
    if not ua:
        raise RuntimeError(
            "SEC requires a User-Agent with contact info. "
            "Set EDGAR_USER_AGENT='Your Name your@email.com'."
        )
    resp = requests.get(
        FACTS_URL.format(cik=TICKER_CIK[ticker]),
        headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    cache_file.write_text(json.dumps(data))
    time.sleep(0.15)  # stay well under SEC's 10 req/s limit
    return data


def _annual_records(units_block: dict, instant: bool) -> list[dict]:
    """Pick annual 10-K records from a concept's unit entries."""
    out = []
    for unit, entries in units_block.items():
        if unit not in ("USD", "shares", "USD/shares"):
            continue
        for e in entries:
            if e.get("form") != "10-K":
                continue
            if instant:
                # Balance-sheet values: keep fiscal-year-end instants
                if e.get("fp") != "FY":
                    continue
            else:
                # Flow values: keep full-year durations (~12 months)
                start, end = e.get("start"), e.get("end")
                if not start or not end:
                    continue
                days = (pd.Timestamp(end) - pd.Timestamp(start)).days
                if not 340 <= days <= 380:
                    continue
            out.append(e)
    return out


def normalize(facts: dict, ticker: str) -> pd.DataFrame:
    """Normalize companyfacts JSON to one row per (ticker, fiscal year)."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    rows: dict[int, dict] = {}
    for metric, tags in CONCEPTS.items():
        instant = metric in INSTANT_METRICS
        for tag in tags:
            if tag not in gaap:
                continue
            recs = _annual_records(gaap[tag].get("units", {}), instant)
            if not recs:
                continue
            # Dedupe by fiscal year, keeping the most recently filed value
            # (later filings restate/confirm earlier ones).
            df = pd.DataFrame(recs)
            df["end"] = pd.to_datetime(df["end"])
            df["fy"] = df["fy"].astype(int)
            df = df.sort_values("filed").groupby("fy").last()
            for fy, rec in df.iterrows():
                rows.setdefault(int(fy), {})[metric] = rec["val"]
            break  # first matching tag wins
    out = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    out.index.name = "fiscal_year"
    out["ticker"] = ticker.upper()
    return out.reset_index()


def load_ticker(ticker: str, cache_dir: str | Path = "data", **kw) -> pd.DataFrame:
    return normalize(fetch_companyfacts(ticker, cache_dir=cache_dir, **kw), ticker)
