"""Tests de régression : des chiffres de référence du stress et du backtest ne doivent pas bouger."""

import pandas as pd
import pytest

from quantlab.backtest.engine import run_backtest
from quantlab.backtest.metrics import performance
from quantlab.backtest.strategy import SMACross
from quantlab.risk.engine import run_stress
from quantlab.risk.scenario import Scenario

KRACH = Scenario("Krach", spot_shocks={"SX5E": -0.30}, vol_shocks={"SX5E": 0.20})

EXPECTED_KRACH = {"T1": -31_213, "T2": -318_975, "T3": -108_936, "T4": -9_431, "T5": 0, "T6": -16_912}


def test_stress_krach_by_position(book, md):
    pnl = run_stress(book, md, [KRACH]).set_index("position")["pnl"]
    for pos, expected in EXPECTED_KRACH.items():
        assert pnl[pos] == pytest.approx(expected, abs=1.0), pos  # tolérance : 1 EUR


def test_backtest_sma_50_200(prices):
    spx = prices["SPX"]
    bt = run_backtest(spx, SMACross(50, 200).signal(spx), cost_bps=5)
    perf = performance(bt)
    assert bt["equity"].iloc[-1] == pytest.approx(1.2279, abs=1e-4)
    assert perf["sharpe"] == pytest.approx(0.218, abs=1e-3)
    assert isinstance(bt.index, pd.DatetimeIndex)
