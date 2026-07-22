"""Fetch SEC's full ticker->CIK map and slim it for the client app."""
import json
import os

import requests

UA = os.environ.get("EDGAR_USER_AGENT", "fundamentals-engine build")
resp = requests.get(
    "https://www.sec.gov/files/company_tickers.json",
    headers={"User-Agent": UA}, timeout=30,
)
resp.raise_for_status()
raw = resp.json()
slim = {
    v["ticker"].upper(): {"cik": v["cik_str"], "name": v["title"]}
    for v in raw.values()
}
out = os.path.join("output", "tickers.json")
os.makedirs("output", exist_ok=True)
with open(out, "w") as f:
    json.dump(slim, f, separators=(",", ":"))
print(f"Wrote {len(slim)} tickers to {out}")
