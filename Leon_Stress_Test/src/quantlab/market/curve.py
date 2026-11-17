"""curve.py — courbe de taux zéro continue, immuable."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class YieldCurve:
    """Courbe de taux zéro, composition continue, maturités en années."""

    tenors: tuple
    rates: tuple

    def __post_init__(self):
        t = np.asarray(self.tenors, dtype=float)
        if len(self.tenors) != len(self.rates) or len(t) < 2:
            raise ValueError("tenors et rates : même longueur, au moins 2 points")
        if np.any(np.diff(t) <= 0) or t[0] <= 0:
            raise ValueError("tenors strictement croissants et positifs")
        if np.any(np.abs(self.rates) > 0.25):
            raise ValueError("taux hors bornes : sont-ils en décimal ?")

    def rate(self, T):
        """Taux zéro interpolé linéairement ; extrapolation plate aux extrémités."""
        return np.interp(T, self.tenors, self.rates)

    def discount(self, T):
        return np.exp(-self.rate(T) * np.asarray(T, dtype=float))

    def forward(self, T1, T2):
        """Taux forward continu entre T1 et T2."""
        if T2 <= T1:
            raise ValueError("T2 doit être > T1")
        return (self.rate(T2) * T2 - self.rate(T1) * T1) / (T2 - T1)

    def shifted(self, bp):
        """Nouvelle courbe choquée en parallèle de `bp` points de base."""
        return YieldCurve(self.tenors, tuple(r + bp / 1e4 for r in self.rates))
