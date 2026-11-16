"""samples.py — marché de référence figé, utilisé par les tests et les exemples."""

from datetime import date

from quantlab.market.curve import YieldCurve
from quantlab.market.data import MarketData


def sample_market(as_of=date(2026, 10, 16)):
    flat = lambda r: YieldCurve((0.25, 1.0, 5.0, 10.0), (r, r, r, r))  # noqa: E731
    return MarketData(
        as_of,
        spots={"SX5E": 4900.0, "EURUSD": 1.17},
        vols={"SX5E": 0.18, "EURUSD": 0.07},
        curves={"EUR": flat(0.02), "USD": flat(0.04)},
        div_yields={"SX5E": 0.03},
    )
