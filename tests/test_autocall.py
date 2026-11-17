"""Autocall : trois cas limites à prix connu, puis le comportement attendu."""

import numpy as np
import pytest

from quantlab.pricing.instruments import Autocall, DigitalOption, EuropeanOption
from quantlab.services import make_market

MD = make_market()  # spot 4 900, vol 18 %, taux 2 %, dividende 3 %
BASE = dict(underlying="SX5E", T=5, S0=4900.0, coupon=0.07, autocall=1.0, protection=0.6)


def test_always_called_at_first_date():
    """Rappel à 0 % : remboursé à 1 an avec un coupon, quel que soit le chemin."""
    ac = Autocall(**{**BASE, "autocall": 0.0, "protection": 0.0})
    r = MD.curves["EUR"].rate(5)
    assert ac.unit_price(MD) == pytest.approx((1 + 0.07) * np.exp(-r * 1.0), rel=1e-12)


def test_never_called_matches_black_scholes():
    """Rappel inatteignable : payoff = 1 - put(B) - (1 - B) x digitale put(B), en % de S0."""
    ac = Autocall(**{**BASE, "autocall": 1e6, "n_paths": 400_000})
    B, S0 = 0.6, 4900.0
    df = np.exp(-MD.curves["EUR"].rate(5) * 5)
    put = EuropeanOption("SX5E", B * S0, 5, call=False).unit_price(MD) / S0
    dig = DigitalOption("SX5E", B * S0, 5, call=False).unit_price(MD)
    amount, when, r = ac.cashflows(MD)
    pv = amount * np.exp(-r * when)
    stderr = pv.std() / np.sqrt(len(pv))
    assert abs(pv.mean() - (df - put - (1 - B) * dig)) < 3 * stderr


def test_outcomes_sum_to_one():
    assert sum(Autocall(**BASE).scenarios(MD).values()) == pytest.approx(1.0)


def test_higher_coupon_higher_price():
    assert Autocall(**{**BASE, "coupon": 0.09}).unit_price(MD) > Autocall(**BASE).unit_price(MD)


def test_investor_is_short_vol():
    """Plus de vol = plus de chances de passer sous la protection : le porteur perd."""
    ac = Autocall(**BASE)
    assert ac.value(MD.bumped_vol("SX5E", 0.05)) < ac.value(MD)


def test_same_seed_same_price():
    """Graine fixe : deux valorisations identiques, donc des Greeks sans bruit de simulation."""
    assert Autocall(**BASE).unit_price(MD) == Autocall(**BASE).unit_price(MD)


def test_invalid_levels_rejected():
    with pytest.raises(ValueError):
        Autocall(**{**BASE, "protection": 1.2})
