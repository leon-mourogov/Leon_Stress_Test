"""scenario.py — un scénario de marché est une DONNÉE : des chocs, appliqués à un MarketData."""

from dataclasses import dataclass, field, replace
from types import MappingProxyType

import numpy as np

from quantlab.market.curve import YieldCurve


def _shift_curve(curve, shock):
    """shock : nombre (bp, parallèle) ou dict {maturité en années: bp}, interpolé sur les piliers."""
    if isinstance(shock, (int, float)):
        bp = np.full(len(curve.tenors), float(shock))
    else:
        tenors = sorted(shock)
        bp = np.interp(curve.tenors, tenors, [shock[t] for t in tenors])
    return YieldCurve(curve.tenors, tuple(float(r) for r in np.asarray(curve.rates) + bp / 1e4))


@dataclass(frozen=True)
class Scenario:
    name: str
    spot_shocks: dict = field(default_factory=dict)  # relatif : -0.10 = -10 %
    vol_shocks: dict = field(default_factory=dict)  # absolu : 0.05 = +5 points de vol
    curve_shocks: dict = field(default_factory=dict)  # en bp, parallèle ou par maturité
    description: str = ""

    def __post_init__(self):
        for name in ("spot_shocks", "vol_shocks", "curve_shocks"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    def apply(self, md):
        unknown = (
            (set(self.spot_shocks) - set(md.spots))
            | (set(self.vol_shocks) - set(md.vols))
            | (set(self.curve_shocks) - set(md.curves))
        )
        if unknown:
            raise KeyError(f"Scénario {self.name!r} : facteurs absents du marché {sorted(unknown)}")
        spots = {k: v * (1 + self.spot_shocks.get(k, 0.0)) for k, v in md.spots.items()}
        vols = {k: max(v + self.vol_shocks.get(k, 0.0), 0.01) for k, v in md.vols.items()}
        curves = {
            ccy: _shift_curve(c, self.curve_shocks[ccy]) if ccy in self.curve_shocks else c
            for ccy, c in md.curves.items()
        }
        return replace(md, spots=spots, vols=vols, curves=curves)


BASE = Scenario("Base")
