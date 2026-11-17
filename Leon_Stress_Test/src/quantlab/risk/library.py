"""library.py — bibliothèque de scénarios : JSON (hypothétiques) et fenêtres historiques."""

import json
from pathlib import Path

import numpy as np

from quantlab.risk.scenario import Scenario


def _curve_shock(value):
    """JSON : les clés de dictionnaire sont TOUJOURS des chaînes -> on les convertit en float."""
    if isinstance(value, dict):
        return {float(t): float(bp) for t, bp in value.items()}
    return float(value)


def load_scenarios(path):
    specs = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios = []
    for s in specs:
        scenarios.append(
            Scenario(
                name=s["name"],
                spot_shocks=s.get("spot_shocks", {}),
                vol_shocks=s.get("vol_shocks", {}),
                curve_shocks={ccy: _curve_shock(v) for ccy, v in s.get("curve_shocks", {}).items()},
                description=s.get("description", ""),
            )
        )
    names = [s.name for s in scenarios]
    if len(names) != len(set(names)):
        raise ValueError("Noms de scénarios en double")
    return scenarios


def worst_window(prices, horizon=20):
    """Date de fin de la pire variation sur `horizon` jours ouvrés."""
    change = prices / prices.shift(horizon) - 1
    end = change.idxmin()
    return prices.index[prices.index.get_loc(end) - horizon], end, float(change.min())


def historical_scenario(prices, start, end, mapping, name=None, vol_window=20):
    """Rejoue une fenêtre historique.

    prices  : DataFrame de prix (une colonne par série historique)
    mapping : {facteur du book: colonne historique}, ex. {"SX5E": "SPX"} (proxy)
    Spot : variation relative start -> end. Vol : variation de la vol réalisée (annualisée)
    entre la fenêtre qui précède `start` et la fenêtre qui finit à `end`.
    """
    rets = np.log(prices).diff()
    spots, vols = {}, {}
    for factor, col in mapping.items():
        spots[factor] = float(prices.loc[end, col] / prices.loc[start, col] - 1)
        before = rets[col].loc[:start].iloc[-vol_window:].std() * np.sqrt(252)
        during = rets[col].loc[:end].iloc[-vol_window:].std() * np.sqrt(252)
        vols[factor] = float(during - before)
    label = name or f"Historique {start:%Y-%m-%d} -> {end:%Y-%m-%d}"
    return Scenario(
        label,
        spot_shocks=spots,
        vol_shocks=vols,
        description=f"Fenêtre {start:%Y-%m-%d} / {end:%Y-%m-%d}, mapping {mapping}",
    )
