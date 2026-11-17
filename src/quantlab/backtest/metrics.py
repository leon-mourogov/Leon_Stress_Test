"""metrics.py — mesures de performance d'un backtest (rendements quotidiens nets)."""

import numpy as np

DAYS = 252


def ann_return(net):
    return float((1 + net).prod() ** (DAYS / len(net)) - 1)


def ann_vol(net):
    return float(net.std() * np.sqrt(DAYS))


def sharpe(net, rf=0.0):
    excess = net - rf / DAYS
    return float(excess.mean() / excess.std() * np.sqrt(DAYS))


def sortino(net, rf=0.0):
    excess = net - rf / DAYS
    downside = np.sqrt((np.minimum(excess, 0) ** 2).mean())  # écart-type des seuls jours négatifs
    return float(excess.mean() / downside * np.sqrt(DAYS))


def max_drawdown(net):
    equity = (1 + net).cumprod()
    return float((equity / equity.cummax() - 1).min())


def performance(bt, benchmark=None, rf=0.0):
    net = bt["net"]
    out = {
        "rendement_annuel": ann_return(net),
        "vol_annuelle": ann_vol(net),
        "sharpe": sharpe(net, rf),
        "sortino": sortino(net, rf),
        "max_drawdown": max_drawdown(net),
        "calmar": ann_return(net) / abs(max_drawdown(net)),
        "turnover_annuel": float(bt["position"].diff().abs().sum() * DAYS / len(bt)),
        "exposition_moyenne": float(bt["position"].abs().mean()),
        "t_stat_sharpe": sharpe(net, rf) * np.sqrt(len(net) / DAYS),
    }
    if benchmark is not None:
        b = benchmark.reindex(net.index).fillna(0.0)
        out["beta"] = float(np.cov(net, b)[0, 1] / b.var())
    return out
