"""analytics.py — statistiques de séries de prix : rendements, volatilités, drawdowns (fonctions pures)."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def simple_returns(prices):
    return prices.pct_change().dropna(how="all")


def log_returns(prices):
    return np.log(prices / prices.shift(1)).dropna(how="all")


def annualized_vol(returns, periods_per_year=TRADING_DAYS):
    return returns.std() * np.sqrt(periods_per_year)


def rolling_vol(returns, window=20, periods_per_year=TRADING_DAYS):
    return returns.rolling(window).std() * np.sqrt(periods_per_year)


def ewma_vol(returns, lam=0.94, periods_per_year=TRADING_DAYS):
    return np.sqrt((returns**2).ewm(alpha=1 - lam, adjust=False).mean() * periods_per_year)


def annualized_return(returns, periods_per_year=TRADING_DAYS):
    return (1 + returns).prod() ** (periods_per_year / len(returns)) - 1


def drawdown(prices):
    return prices / prices.cummax() - 1


def max_drawdown(prices):
    return drawdown(prices).min()


def drawdown_stats(prices):
    dd = drawdown(prices)
    if dd.min() == 0:
        return {
            "max_drawdown": 0.0,
            "peak": None,
            "trough": None,
            "recovery": None,
            "days_to_trough": None,
            "days_to_recover": None,
        }
    trough = dd.idxmin()
    peak = prices.loc[:trough].idxmax()
    after = prices.loc[trough:]
    rec = after[after >= prices.loc[peak]]
    recovery = rec.index[0] if len(rec) else None
    return {
        "max_drawdown": float(dd.min()),
        "peak": peak,
        "trough": trough,
        "recovery": recovery,
        "days_to_trough": len(prices.loc[peak:trough]) - 1,
        "days_to_recover": None if recovery is None else len(prices.loc[trough:recovery]) - 1,
    }


def summary_table(prices, periods_per_year=TRADING_DAYS):
    r = simple_returns(prices)
    return pd.DataFrame(
        {
            "ann_return": annualized_return(r, periods_per_year),
            "ann_vol": annualized_vol(r, periods_per_year),
            "max_drawdown": max_drawdown(prices),
            "skew": r.skew(),
            "excess_kurtosis": r.kurt(),
            "worst_day": r.min(),
            "best_day": r.max(),
        }
    )
