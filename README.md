# fundamentals-engine

A reproducible financial-statement analysis pipeline built on primary-source data.
It pulls as-filed 10-K figures from the **SEC EDGAR XBRL companyfacts API** and
market data via **yfinance** (Stooq fallback), computes a full ratio suite,
benchmarks any subject ticker against a peer set (default: **INTC** vs
**AMD, NVDA, TSM**), and renders a self-contained HTML dashboard.

Originated as a graduate financial statement analysis project (USF M.S. Financial
Technology, FIN 6465) and rebuilt as code so every number is traceable to a filing
and every chart regenerates with one command.

## Why this exists

Most student equity analyses are spreadsheets with hand-keyed numbers: not
reproducible, not auditable, dead the moment a new 10-K drops. This pipeline treats
the analysis as software:

- **Primary sources only** — figures come from SEC XBRL filings, not a data vendor's
  cleaned copy. Concept-tag fallbacks handle the fact that issuers file under
  different us-gaap tags.
- **Restatement-aware** — when the same fiscal year appears in multiple filings, the
  most recently filed value wins.
- **Graceful degradation** — missing concepts produce NaN, never a crash; market data
  (yfinance, Stooq fallback) is optional and the operating comparison runs without it.

## What it computes

| Category | Metrics |
|---|---|
| Margins | gross, operating, net, FCF margin, R&D intensity |
| Returns | ROE, ROA |
| Liquidity | current ratio, quick ratio |
| Leverage | debt/equity, interest coverage |
| Efficiency & growth | asset turnover, revenue & net income growth (YoY) |
| Valuation (optional) | P/E, P/S, P/FCF from latest closes (yfinance / Stooq) |

Output: a single-file HTML dashboard (KPI strip, 5-year trend charts, peer bar
charts, direction-aware peer rankings) plus a tidy `ratios.csv`.

## Interactive app

The published site (GitHub Pages) is a client-side SPA (`app/index.html`) that
fetches EDGAR companyfacts **directly in the browser** — add any US filer by
ticker, view its individual fundamentals (KPIs, trends, full ratio history), and
switch to the **Compare** tab for multi-company charts and a direction-aware
best-in-group snapshot table. The ratio logic is a JS port of `metrics.py`;
`scripts/build_tickers.py` publishes the SEC ticker→CIK map at build time so
lookup works offline from EDGAR's search. Added companies persist in
localStorage. The CI-generated static report remains at `/dashboard.html`.

## Quick start

```bash
pip install -r requirements.txt
export EDGAR_USER_AGENT="Your Name your@email.com"   # SEC fair-access policy
python -m fundamentals.cli --subject INTC --peers AMD NVDA TSM
# open output/dashboard.html
```

Run it for any covered ticker set:

```bash
python -m fundamentals.cli --subject NVDA --peers AMD INTC QCOM --no-prices
```

## Architecture

```
src/fundamentals/
  edgar.py    # fetch + cache companyfacts JSON; normalize to tidy annual rows
  metrics.py  # ratio computation (pure functions, NaN-safe)
  market.py   # yfinance prices/snapshots with keyless Stooq fallback
  peers.py    # peer snapshot table, valuation multiples, direction-aware ranking
  report.py   # matplotlib charts -> base64 -> single-file HTML dashboard
  cli.py      # argparse entry point
tests/        # pytest suite over synthetic statements with known-answer ratios
```

Design choices worth noting:

1. **Tag fallback lists.** `Revenues` vs `RevenueFromContractWithCustomerExcludingAssessedTax`
   vs `SalesRevenueNet` — the pipeline tries each in priority order per metric.
2. **Duration filtering.** Flow metrics keep only ~12-month periods from 10-K forms,
   which strips out the quarterly and cumulative entries EDGAR mixes into the same
   concept.
3. **Instant vs. duration handling.** Balance-sheet concepts are matched on fiscal-
   year-end instants; income/cash-flow concepts on annual durations.

## Testing

```bash
python -m pytest tests/ -q
```

Tests validate ratio math against hand-computed answers, NaN behavior on missing
inputs, and direction-aware peer ranking (lower debt/equity ranks better; higher
margin ranks better).

## Limitations

- Ticker→CIK map is hardcoded for the semiconductor set; extend `TICKER_CIK` or wire
  up SEC's `company_tickers.json` for full coverage.
- Foreign private issuers (e.g., TSM files 20-F) may expose fewer us-gaap concepts;
  affected ratios show as NaN rather than being estimated.
- Valuation uses latest close against last-fiscal-year fundamentals — a deliberate
  simplification, flagged in the dashboard footer.

*Not investment advice. Data © respective filers via SEC EDGAR.*
