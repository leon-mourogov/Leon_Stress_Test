"""data.py — instantané immuable du marché à une date."""

from dataclasses import dataclass, field, replace
from datetime import date
from types import MappingProxyType

from quantlab.errors import DataQualityError


def _frozen(d):
    return MappingProxyType(dict(d))


@dataclass(frozen=True)
class MarketData:
    as_of: date
    spots: dict  # {"SX5E": 4900.0, "EURUSD": 1.17}
    vols: dict  # vol implicite ATM, décimal
    curves: dict  # {"EUR": YieldCurve, "USD": YieldCurve}
    div_yields: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in ("spots", "vols", "curves", "div_yields"):
            object.__setattr__(self, name, _frozen(getattr(self, name)))
        for k, v in self.spots.items():
            if v <= 0:
                raise DataQualityError(f"Spot {k} non positif : {v}")
        for k, v in self.vols.items():
            if not 0 < v < 3:
                raise DataQualityError(f"Vol {k} hors bornes : {v} (décimal attendu)")

    def spot(self, name):
        try:
            return self.spots[name]
        except KeyError:
            raise KeyError(f"Spot absent du marché : {name}") from None

    def bumped_spot(self, name, rel):
        spots = dict(self.spots)
        spots[name] = spots[name] * (1 + rel)
        return replace(self, spots=spots)

    def bumped_vol(self, name, abs_bump):
        vols = dict(self.vols)
        vols[name] = vols[name] + abs_bump
        return replace(self, vols=vols)

    def shifted_curve(self, ccy, bp):
        curves = dict(self.curves)
        curves[ccy] = curves[ccy].shifted(bp)
        return replace(self, curves=curves)
