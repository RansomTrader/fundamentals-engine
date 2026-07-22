"""Precompute market data (yfinance) for the client app's Market tab.

Writes output/market/{TICKER}.json:
{"price", "market_cap", "year_high", "year_low", "history": [[ms, close]...], "asof"}

Never fails the build — every ticker is wrapped; partial data beats no data.
"""
import datetime
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_universe import read_universe  # noqa: E402

import yfinance as yf  # noqa: E402


def main() -> None:
    tickers = read_universe()
    out_dir = pathlib.Path("output/market")
    out_dir.mkdir(parents=True, exist_ok=True)
    asof = datetime.date.today().isoformat()

    hist = None
    try:
        hist = yf.download(
            tickers=" ".join(tickers), period="5y", interval="1wk",
            group_by="ticker", auto_adjust=True, progress=False, threads=True,
        )
    except Exception as e:  # noqa: BLE001
        print("batch history failed:", e)

    built = 0
    for t in tickers:
        rec = {"price": None, "market_cap": None, "year_high": None,
               "year_low": None, "history": [], "asof": asof}
        try:
            if hist is not None and t in getattr(hist.columns, "levels", [[]])[0]:
                closes = hist[t]["Close"].dropna()
                rec["history"] = [
                    [int(ts.timestamp() * 1000), round(float(px), 2)]
                    for ts, px in closes.items()
                ]
                if rec["history"]:
                    rec["price"] = rec["history"][-1][1]
        except Exception as e:  # noqa: BLE001
            print(f"  hist {t}: {e}")
        try:
            fi = yf.Ticker(t).fast_info
            def g(key):
                try:
                    v = fi[key]
                    return float(v) if v is not None else None
                except Exception:
                    return None
            rec["price"] = g("lastPrice") or rec["price"]
            rec["market_cap"] = g("marketCap")
            rec["year_high"] = g("yearHigh")
            rec["year_low"] = g("yearLow")
            time.sleep(0.15)
        except Exception as e:  # noqa: BLE001
            print(f"  info {t}: {e}")
        if rec["price"] or rec["history"]:
            (out_dir / f"{t}.json").write_text(json.dumps(rec, separators=(",", ":")))
            built += 1
    print(f"Market data for {built}/{len(tickers)} tickers")


if __name__ == "__main__":
    main()
