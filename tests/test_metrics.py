import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest
from fundamentals.metrics import compute_ratios
from fundamentals.peers import peer_table, rank_vs_peers


def sample_frame():
    rows = []
    base = {
        "AAA": dict(revenue=100.0, cost_of_revenue=60.0, operating_income=20.0,
                    net_income=15.0, assets=200.0, equity=100.0,
                    current_assets=80.0, current_liabilities=40.0, inventory=10.0,
                    total_debt_lt=30.0, total_debt_st=5.0, interest_expense=2.0,
                    operating_cash_flow=25.0, capex=10.0, rnd_expense=12.0),
        "BBB": dict(revenue=50.0, cost_of_revenue=20.0, operating_income=18.0,
                    net_income=14.0, assets=90.0, equity=60.0,
                    current_assets=40.0, current_liabilities=10.0, inventory=4.0,
                    total_debt_lt=5.0, total_debt_st=0.0, interest_expense=0.5,
                    operating_cash_flow=20.0, capex=4.0, rnd_expense=10.0),
    }
    for tkr, vals in base.items():
        for i, fy in enumerate([2023, 2024, 2025]):
            growth = 1.0 + 0.1 * i
            rows.append({"ticker": tkr, "fiscal_year": fy,
                         **{k: v * growth for k, v in vals.items()}})
    return pd.DataFrame(rows)


def test_core_ratios():
    r = compute_ratios(sample_frame())
    a25 = r[(r.ticker == "AAA") & (r.fiscal_year == 2025)].iloc[0]
    assert a25.gross_margin == pytest.approx(0.40)
    assert a25.operating_margin == pytest.approx(0.20)
    assert a25.net_margin == pytest.approx(0.15)
    assert a25.roe == pytest.approx(0.15)
    assert a25.current_ratio == pytest.approx(2.0)
    assert a25.debt_to_equity == pytest.approx(0.35)
    assert a25.free_cash_flow == pytest.approx((25 - 10) * 1.2)
    assert a25.revenue_growth == pytest.approx((1.2 / 1.1) - 1)


def test_missing_inputs_yield_nan_not_crash():
    df = pd.DataFrame([{"ticker": "CCC", "fiscal_year": 2025, "revenue": 10.0}])
    r = compute_ratios(df)
    assert pd.isna(r.iloc[0].roe)
    assert pd.isna(r.iloc[0].debt_to_equity)


def test_peer_rank_direction():
    r = compute_ratios(sample_frame())
    tbl = peer_table(r)
    ranks = rank_vs_peers(tbl, "BBB")
    # BBB has higher margins -> rank 1; lower debt/equity should also rank 1
    assert ranks.loc["gross_margin", "rank"] == "1/2"
    assert ranks.loc["debt_to_equity", "rank"] == "1/2"


def synthetic_facts():
    """Minimal companyfacts JSON: FY2025 = 4 quarters of revenue, Q4 omitted
    from quarterly filings so it must be derived from annual - Q1..Q3."""
    def dur(start, end, val, form, fy="2025", fp="Q1"):
        return {"start": start, "end": end, "val": val, "form": form,
                "fy": int(fy), "fp": fp, "filed": end}
    revenue_entries = [
        dur("2025-01-01", "2025-03-31", 10.0, "10-Q"),
        dur("2025-04-01", "2025-06-30", 12.0, "10-Q"),
        dur("2025-07-01", "2025-09-30", 11.0, "10-Q"),
        dur("2025-01-01", "2025-12-31", 47.0, "10-K", fp="FY"),  # implies Q4 = 14
    ]
    equity_entries = [
        {"end": "2025-09-30", "val": 60.0, "form": "10-Q", "fy": 2025,
         "fp": "Q3", "filed": "2025-10-30"},
        {"end": "2025-12-31", "val": 65.0, "form": "10-K", "fy": 2025,
         "fp": "FY", "filed": "2026-02-01"},
    ]
    ni_entries = [
        dur("2025-01-01", "2025-03-31", 1.0, "10-Q"),
        dur("2025-04-01", "2025-06-30", 1.5, "10-Q"),
        dur("2025-07-01", "2025-09-30", 1.2, "10-Q"),
        dur("2025-01-01", "2025-12-31", 5.2, "10-K", fp="FY"),  # Q4 = 1.5
    ]
    return {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": revenue_entries}},
        "NetIncomeLoss": {"units": {"USD": ni_entries}},
        "StockholdersEquity": {"units": {"USD": equity_entries}},
    }}}


def test_quarterly_q4_derivation_and_ttm():
    from fundamentals.edgar import normalize_quarterly, latest_instants
    from fundamentals.metrics import ttm_summary
    facts = synthetic_facts()
    q = normalize_quarterly(facts)
    assert len(q) == 4
    assert q["revenue"].iloc[-1] == pytest.approx(14.0)   # derived Q4
    inst = latest_instants(facts)
    assert inst["equity"]["val"] == 65.0                   # latest end wins
    ttm = ttm_summary(q, inst)
    assert ttm["revenue"] == pytest.approx(47.0)
    assert ttm["net_income"] == pytest.approx(5.2)
    assert ttm["net_margin"] == pytest.approx(5.2 / 47.0)
    assert ttm["roe"] == pytest.approx(5.2 / 65.0)
