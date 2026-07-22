"""Market data: prices and valuation inputs.

Primary source is yfinance (Yahoo Finance); Stooq's keyless daily CSV
is the fallback so the pipeline still produces valuation multiples if
Yahoo rate-limits or changes its endpoints. Every function degrades to
None rather than raising, so the operating analysis never depends on
market data being available.
"""
from __future__ import annotations

import io

import pandas as pd
import requests

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"


def _stooq_price(ticker: str) -> float | None:
    try:
        resp = requests.get(STOOQ_URL.format(symbol=ticker.lower()), timeout=15)
        resp.raise_for_status()
        px = pd.read_csv(io.StringIO(resp.text))
        return float(px["Close"].iloc[-1])
    except Exception:
        return None


def latest_price(ticker: str) -> float | None:
    """Latest close: yfinance first, Stooq fallback."""
    if yf is not None:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist):
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return _stooq_price(ticker)


def snapshot(ticker: str) -> dict:
    """Market snapshot for the dashboard: price plus Yahoo's own
    trailing multiples, useful as a sanity check against the multiples
    this pipeline computes from filings."""
    out: dict = {"price": latest_price(ticker), "market_cap": None,
                 "yahoo_trailing_pe": None, "yahoo_ps": None}
    if yf is None:
        return out
    try:
        info = yf.Ticker(ticker).info
        out["market_cap"] = info.get("marketCap")
        out["yahoo_trailing_pe"] = info.get("trailingPE")
        out["yahoo_ps"] = info.get("priceToSalesTrailing12Months")
        if out["price"] is None:
            out["price"] = info.get("currentPrice")
    except Exception:
        pass
    return out


def price_history(ticker: str, period: str = "5y") -> pd.DataFrame | None:
    """Daily OHLCV history via yfinance (None if unavailable)."""
    if yf is None:
        return None
    try:
        hist = yf.Ticker(ticker).history(period=period)
        return hist if len(hist) else None
    except Exception:
        return None
