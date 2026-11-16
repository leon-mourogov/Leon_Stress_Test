"""engine.py — backtest vectorisé : signal -> position (décalée) -> P&L net de coûts."""

import pandas as pd


def run_backtest(prices, signal, cost_bps=5.0):
    """prices, signal : Series alignées (même index). signal = exposition voulue à la clôture de t.

    La position détenue pendant la journée t+1 est le signal calculé à la clôture de t.
    cost_bps : coût par unité de notionnel échangée, en points de base (spread + commission).
    """
    if not prices.index.equals(signal.index):
        raise ValueError("prices et signal doivent avoir le même index")
    rets = prices.pct_change()
    position = signal.shift(1).fillna(0.0)  # on trade à la clôture, on porte le lendemain
    turnover = position.diff().abs().fillna(position.abs())
    gross = position * rets
    costs = turnover * cost_bps / 1e4
    net = (gross - costs).fillna(0.0)
    return pd.DataFrame(
        {
            "price": prices,
            "signal": signal,
            "position": position,
            "ret": rets,
            "gross": gross.fillna(0.0),
            "costs": costs,
            "net": net,
            "equity": (1 + net).cumprod(),
        }
    )
