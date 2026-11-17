"""var.py — VaR et Expected Shortfall historiques par revalorisation complète."""

import numpy as np
import pandas as pd

from quantlab.risk.engine import value_book
from quantlab.risk.scenario import Scenario


def historical_scenarios(prices, mapping, window=500):
    """Un scénario par jour : les rendements observés appliqués comme chocs relatifs."""
    rets = prices[list(mapping.values())].pct_change().dropna().iloc[-window:]
    return [
        Scenario(f"{d:%Y-%m-%d}", spot_shocks={f: float(row[c]) for f, c in mapping.items()})
        for d, row in rets.iterrows()
    ]


def pnl_distribution(positions, md, scenarios, base="EUR"):
    """Série des P&L du book (un par scénario), revalorisation complète."""
    v0 = sum(value_book(positions, md, base).values())
    pnl = {sc.name: sum(value_book(positions, sc.apply(md), base).values()) - v0 for sc in scenarios}
    return pd.Series(pnl, name="pnl")


def var_es(pnl, level=0.99):
    """VaR et ES exprimées en pertes positives. VaR = quantile, ES = moyenne au-delà."""
    losses = -np.asarray(pnl)
    var = float(np.quantile(losses, level))
    es = float(losses[losses >= var].mean())
    return var, es
