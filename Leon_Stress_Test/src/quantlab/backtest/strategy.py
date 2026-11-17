"""strategy.py — une stratégie = un objet qui transforme des prix en signal."""

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Strategy(ABC):
    """Contrat : signal(prices) renvoie une Series alignée sur prices, connue à la clôture de t."""

    @abstractmethod
    def signal(self, prices: pd.Series) -> pd.Series: ...

    @property
    def name(self):
        params = ", ".join(f"{k}={v}" for k, v in vars(self).items() if not isinstance(v, Strategy))
        inner = [v.name for v in vars(self).values() if isinstance(v, Strategy)]
        return f"{type(self).__name__}({', '.join(inner + ([params] if params else []))})"


class BuyAndHold(Strategy):
    def signal(self, prices):
        return pd.Series(1.0, index=prices.index)


class SMACross(Strategy):
    def __init__(self, fast=50, slow=200, short=False):
        if fast >= slow:
            raise ValueError("fast doit être < slow")
        self.fast, self.slow, self.short = fast, slow, short

    def signal(self, prices):
        f, s = prices.rolling(self.fast).mean(), prices.rolling(self.slow).mean()
        sig = np.where(f > s, 1.0, -1.0 if self.short else 0.0)
        return pd.Series(sig, index=prices.index).where(s.notna(), 0.0)


class Momentum(Strategy):
    """Signe du rendement passé sur `lookback` jours, en sautant les `skip` derniers jours."""

    def __init__(self, lookback=252, skip=21):
        self.lookback, self.skip = lookback, skip

    def signal(self, prices):
        past = prices.shift(self.skip) / prices.shift(self.lookback) - 1
        return np.sign(past).fillna(0.0)


class VolTarget(Strategy):
    """Enveloppe une stratégie : met à l'échelle son signal pour viser une volatilité cible."""

    def __init__(self, inner, target=0.10, window=60, max_leverage=2.0):
        self.inner, self.target, self.window, self.max_leverage = inner, target, window, max_leverage

    def signal(self, prices):
        realized = prices.pct_change().rolling(self.window).std() * np.sqrt(252)
        scale = (self.target / realized).clip(upper=self.max_leverage).fillna(0.0)
        return self.inner.signal(prices) * scale
