"""Explication du P&L par les Greeks."""

import pytest

from quantlab.risk.explain import taylor_pnl
from quantlab.risk.scenario import Scenario

SMALL = Scenario("Petit", spot_shocks={"SX5E": -0.02}, vol_shocks={"SX5E": 0.01})
KRACH = Scenario("Krach", spot_shocks={"SX5E": -0.30}, vol_shocks={"SX5E": 0.20})


@pytest.fixture
def positions(book):
    return {p.id: p.instrument for p in book}


def test_decomposition_adds_up(positions, md):
    r = taylor_pnl(positions["T2"], md, KRACH.apply(md))
    assert r["delta"] + r["gamma"] + r["vega"] + r["residu"] == pytest.approx(r["full"], abs=1e-6)


@pytest.mark.parametrize("pos", ["T1", "T2", "T3"])
def test_small_shock_is_well_explained(positions, md, pos):
    r = taylor_pnl(positions[pos], md, SMALL.apply(md))
    assert abs(r["residu"]) < 0.05 * abs(r["full"])  # résidu < 5 % du P&L


def test_reference_values_from_lesson_33(positions, md):
    r = taylor_pnl(positions["T2"], md, SMALL.apply(md))
    assert r["full"] == pytest.approx(-11_302, abs=1)
    assert r["residu"] == pytest.approx(-308, abs=1)
