"""Tests du modèle de Black-Scholes : relations sans modèle, Greeks, vol implicite."""

import itertools

import numpy as np
import pytest

from quantlab.pricing.bs import bs_greeks, bs_price
from quantlab.pricing.implied import ImpliedVolError, implied_vol

S, R, Q = 100.0, 0.03, 0.01
GRID = list(
    itertools.product(
        [60, 80, 100, 120, 150],  # strikes
        [0.1, 0.5, 1.0, 2.0, 5.0],  # maturités
        [0.10, 0.40],
    )
)  # vols  -> 5 x 5 x 2 = 50 cas


@pytest.mark.parametrize("K, T, sigma", GRID)
def test_put_call_parity(K, T, sigma):
    call = bs_price(S, K, T, R, sigma, Q, call=True)
    put = bs_price(S, K, T, R, sigma, Q, call=False)
    forward = S * np.exp(-Q * T) - K * np.exp(-R * T)
    assert call - put == pytest.approx(forward, abs=1e-10)


@pytest.mark.parametrize("K, T, sigma", GRID)
def test_price_bounds(K, T, sigma):
    call = bs_price(S, K, T, R, sigma, Q, call=True)
    lower = max(S * np.exp(-Q * T) - K * np.exp(-R * T), 0.0)
    assert lower - 1e-12 <= call <= S * np.exp(-Q * T)


def test_hull_reference_value():
    # Hull, exemple 15.6 : S=42, K=40, r=10 %, sigma=20 %, T=0,5 -> call 4,76 ; put 0,81
    assert bs_price(42, 40, 0.5, 0.10, 0.20, call=True) == pytest.approx(4.76, abs=0.005)
    assert bs_price(42, 40, 0.5, 0.10, 0.20, call=False) == pytest.approx(0.81, abs=0.005)


@pytest.mark.parametrize("call", [True, False])
def test_delta_matches_finite_difference(call):
    h = 0.01
    up = bs_price(S + h, 105, 1.0, R, 0.2, Q, call)
    dn = bs_price(S - h, 105, 1.0, R, 0.2, Q, call)
    assert bs_greeks(S, 105, 1.0, R, 0.2, Q, call)["delta"] == pytest.approx((up - dn) / (2 * h), rel=1e-6)


@pytest.mark.parametrize("K", [70, 100, 130])
@pytest.mark.parametrize("call", [True, False])
def test_implied_vol_round_trip(K, call):
    price = bs_price(S, K, 0.75, R, 0.27, Q, call)
    assert implied_vol(price, S, K, 0.75, R, Q, call) == pytest.approx(0.27, abs=1e-8)


def test_implied_vol_rejects_price_below_intrinsic():
    with pytest.raises(ImpliedVolError):
        implied_vol(0.5, 100, 90, 0.5, 0.03)
