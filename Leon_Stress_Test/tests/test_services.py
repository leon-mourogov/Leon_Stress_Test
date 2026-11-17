"""Tests de la couche services : ce que l'app et l'API affichent."""

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from quantlab.market.samples import sample_market
from quantlab.risk.engine import load_book
from quantlab.risk.library import load_scenarios
from quantlab.risk.scenario import BASE
from quantlab.services import make_market, price, stress_table, to_excel_bytes

CALL = {"type": "european", "underlying": "SX5E", "K": 5000.0, "T": 1.0, "call": True, "notional": 200}


def test_vega_is_per_vol_point():
    md = make_market(vol=0.18)
    up = make_market(vol=0.19)
    res = price(CALL, md)
    assert price(CALL, up)["valeur"] - res["valeur"] == pytest.approx(res["vega_1pt"], rel=0.01)


def test_delta_cash_is_pnl_for_one_percent():
    md, up = make_market(spot=4900.0), make_market(spot=4900.0 * 1.01)
    res = price(CALL, md)
    assert price(CALL, up)["valeur"] - res["valeur"] == pytest.approx(
        res["delta_cash_1pct"] + res["gamma_cash_1pct"], rel=0.01
    )


def test_note_quoted_in_percent_of_nominal():
    spec = {
        "type": "cpn",
        "underlying": "SX5E",
        "T": 1.0,
        "participation": 0.6,
        "S0": 4900.0,
        "notional": 1e6,
    }
    res = price(spec, make_market())
    assert res["cotation"] == "% du nominal"
    assert 90 < res["prix_pct"] < 110


def test_stress_total_is_sum_of_positions():
    root = Path(__file__).resolve().parents[1]
    grid = stress_table(
        load_book(root / "config" / "book.json"),
        sample_market(),
        [BASE, *load_scenarios(root / "config" / "scenarios.json")],
    )
    pd.testing.assert_series_equal(grid.drop(columns="TOTAL").sum(axis=1), grid["TOTAL"], check_names=False)
    assert grid.loc[BASE.name, "TOTAL"] == pytest.approx(0.0, abs=1e-6)


def test_excel_export_roundtrip():
    df = pd.DataFrame({"a": [1.0, 2.0]}, index=["x", "y"])
    back = pd.read_excel(BytesIO(to_excel_bytes({"Stress": df})), index_col=0)
    pd.testing.assert_frame_equal(back, df, check_dtype=False)  # Excel relit 1.0 comme un entier
