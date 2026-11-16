"""Statistiques de séries de prix : drawdowns, rendements, volatilités sur des cas calculables à la main."""

import numpy as np
import pandas as pd

from quantlab.analytics import (
    drawdown_stats,
    ewma_vol,
    log_returns,
    max_drawdown,
    rolling_vol,
    simple_returns,
)

PRICES = pd.Series([100, 110, 99, 105, 121, 90, 95], index=pd.bdate_range("2026-01-05", periods=7))


def test_max_drawdown_is_from_peak_to_trough():
    assert abs(max_drawdown(PRICES) - (90 / 121 - 1)) < 1e-12


def test_drawdown_without_recovery():
    stats = drawdown_stats(PRICES)
    assert stats["recovery"] is None and stats["days_to_trough"] == 1


def test_rising_series_has_no_drawdown():
    up = pd.Series([1.0, 2.0, 3.0], index=pd.bdate_range("2026-01-05", periods=3))
    assert drawdown_stats(up)["max_drawdown"] == 0.0


def test_returns_compound_to_total_performance():
    total = PRICES.iloc[-1] / PRICES.iloc[0]
    assert abs((1 + simple_returns(PRICES)).prod() - total) < 1e-12
    assert abs(np.exp(log_returns(PRICES).sum()) - total) < 1e-12


def test_constant_returns_have_zero_volatility():
    const = pd.Series(0.01, index=pd.bdate_range("2026-01-05", periods=30))
    assert rolling_vol(const, 20).dropna().abs().max() < 1e-12


def test_ewma_first_update():
    vol = ewma_vol(pd.Series([0.0, 0.01]), lam=0.94, periods_per_year=1).iloc[-1]
    assert abs(vol - np.sqrt(0.06) * 0.01) < 1e-15
