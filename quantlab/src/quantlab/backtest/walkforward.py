"""walkforward.py — optimisation dans l'échantillon, validation hors échantillon."""

import itertools

import pandas as pd

from quantlab.backtest.engine import run_backtest
from quantlab.backtest.metrics import sharpe


def grid_search(prices, make_strategy, grid, start, end, cost_bps=5.0):
    """Sharpe de chaque combinaison de paramètres sur [start, end].

    Le signal est calculé sur TOUT l'historique disponible jusqu'à `end` (les moyennes
    mobiles ont besoin du passé), mais le Sharpe n'est mesuré que sur [start, end].
    """
    hist = prices.loc[:end]
    rows = []
    for values in itertools.product(*grid.values()):
        params = dict(zip(grid.keys(), values, strict=True))
        try:
            strat = make_strategy(**params)
        except ValueError:
            continue  # combinaison invalide (ex. fast >= slow)
        bt = run_backtest(hist, strat.signal(hist), cost_bps)
        rows.append({**params, "sharpe": sharpe(bt["net"].loc[start:end])})
    return pd.DataFrame(rows).sort_values("sharpe", ascending=False)


def walk_forward(
    prices, make_strategy, grid, train_years=3, first_test_year=2019, last_test_year=2025, cost_bps=5.0
):
    """Chaque année : choisir les paramètres sur les `train_years` précédentes, les appliquer à l'année."""
    pieces, choices = [], []
    for year in range(first_test_year, last_test_year + 1):
        train_start, train_end = f"{year - train_years}-01-01", f"{year - 1}-12-31"
        best = grid_search(prices, make_strategy, grid, train_start, train_end, cost_bps).iloc[0]
        params = {
            k: type(v)(best[k])
            for k, v in zip(grid.keys(), next(itertools.product(*grid.values())), strict=True)
        }
        hist = prices.loc[: f"{year}-12-31"]
        bt = run_backtest(hist, make_strategy(**params).signal(hist), cost_bps)
        pieces.append(bt["net"].loc[f"{year}-01-01" : f"{year}-12-31"])
        choices.append(
            {"annee": year, **params, "sharpe_train": best["sharpe"], "sharpe_test": sharpe(pieces[-1])}
        )
    return pd.concat(pieces), pd.DataFrame(choices)
