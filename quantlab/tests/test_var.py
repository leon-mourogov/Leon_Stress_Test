"""VaR et ES historiques."""

import numpy as np
import pandas as pd
import pytest

from quantlab.risk.engine import Position
from quantlab.risk.var import historical_scenarios, pnl_distribution, var_es


def test_var_es_on_known_series():
    pnl = -np.arange(1, 101)  # pertes de 1 à 100
    var, es = var_es(pnl, 0.99)
    assert var == pytest.approx(99.01)
    assert es == pytest.approx(100.0)


def test_es_is_never_below_var():
    pnl = np.random.default_rng(0).standard_t(3, 1000)
    for level in (0.95, 0.975, 0.99):
        var, es = var_es(pnl, level)
        assert es >= var


def test_historical_scenarios_window_and_names(prices):
    scen = historical_scenarios(prices, {"SX5E": "SPX"}, window=250)
    assert len(scen) == 250
    assert scen[-1].name == f"{prices.index[-1]:%Y-%m-%d}"


def test_pnl_distribution_linear_position(md):
    """Un forward ne contient aucune optionalité : son P&L est une fonction affine du choc."""
    from quantlab.pricing.instruments import Forward

    book = [Position("F", Forward("SX5E", 4900, 1.0, notional=10))]
    prices = pd.DataFrame({"SPX": [100.0, 101.0, 99.0]}, index=pd.bdate_range("2026-01-01", periods=3))
    pnl = pnl_distribution(book, md, historical_scenarios(prices, {"SX5E": "SPX"}))
    delta = 10 * 4900 * np.exp(-0.03)  # notionnel x S x e^{-qT}
    assert list(pnl) == pytest.approx([0.01 * delta, (99 / 101 - 1) * delta])
