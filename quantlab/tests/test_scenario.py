"""Scénarios de stress : chocs de spot, de vol et de courbe."""

import json

import pytest

from quantlab.risk.library import load_scenarios
from quantlab.risk.scenario import BASE, Scenario


def test_base_scenario_changes_nothing(md):
    assert BASE.apply(md) == md


def test_scenario_is_immutable():
    sc = Scenario("x", spot_shocks={"SX5E": -0.1})
    with pytest.raises(TypeError):
        sc.spot_shocks["SX5E"] = -0.5


def test_unknown_factor_is_rejected(md):
    with pytest.raises(KeyError, match="NKY"):
        Scenario("x", spot_shocks={"NKY": -0.1}).apply(md)


def test_vol_floor(md):
    shocked = Scenario("x", vol_shocks={"SX5E": -0.50}).apply(md)
    assert shocked.vols["SX5E"] == pytest.approx(0.01)


def test_json_curve_keys_are_converted(tmp_path, md):
    path = tmp_path / "sc.json"  # tmp_path : dossier temporaire propre à ce test
    path.write_text(json.dumps([{"name": "Pente", "curve_shocks": {"EUR": {"0.25": 0, "2": 25, "10": 100}}}]))
    rates = load_scenarios(path)[0].apply(md).curves["EUR"].rates
    assert rates[-1] == pytest.approx(0.03)  # 10 ans : +100 bp (et pas +25 bp)
