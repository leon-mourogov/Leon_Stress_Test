"""Validation croisée avec QuantLib (sautée si QuantLib n'est pas installé)."""

import pytest

ql = pytest.importorskip("QuantLib")

from quantlab.pricing.bs import bs_price  # noqa: E402
from quantlab.pricing.ql_check import ql_european  # noqa: E402


@pytest.mark.parametrize("K", [4000, 4500, 4900, 5300, 6000])
@pytest.mark.parametrize("days", [30, 182, 365, 1826])
@pytest.mark.parametrize("call", [True, False])
def test_european_matches_quantlib(K, days, call):
    ref = ql_european(4900, K, days, 0.02, 0.18, 0.03, call)["price"]
    assert bs_price(4900, K, days / 365, 0.02, 0.18, 0.03, call) == pytest.approx(ref, abs=1e-8)
