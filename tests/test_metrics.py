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
