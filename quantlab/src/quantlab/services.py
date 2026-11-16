"""services.py — les fonctions qu'appellent l'app Streamlit et l'API : aucune logique dans l'interface."""

from dataclasses import replace

import numpy as np
import pandas as pd

from quantlab.market.curve import YieldCurve
from quantlab.market.samples import sample_market
from quantlab.pricing.instruments import build


def make_market(spot=None, vol=None, rate=None, div=None, underlying="SX5E", ccy="EUR", base=None):
    """Marché de référence, avec les paramètres saisis par l'utilisateur pour un sous-jacent."""
    md = base or sample_market()
    spots, vols = dict(md.spots), dict(md.vols)
    curves, divs = dict(md.curves), dict(md.div_yields)
    if spot is not None:
        spots[underlying] = float(spot)
    if vol is not None:
        vols[underlying] = float(vol)
    if rate is not None:
        curves[ccy] = YieldCurve((0.25, 1.0, 5.0, 10.0), (float(rate),) * 4)
    if div is not None:
        divs[underlying] = float(div)
    return replace(md, spots=spots, vols=vols, curves=curves, div_yields=divs)


PERCENT_QUOTED = {"cpn", "digital", "autocall"}  # produits cotés en % du nominal, pas en points d'indice


def price(spec, md):
    """Prix et Greeks d'un produit, avec les unités qu'un vendeur attend."""
    ins = build(spec)
    S = md.spot(ins.underlying)
    g = ins.greeks(md)
    value, unit = float(ins.value(md)), float(ins.unit_price(md))
    in_pct = spec["type"] in PERCENT_QUOTED
    return {
        "valeur": value,
        "prix_unitaire": unit,
        "prix_pct": unit * 100 if in_pct else unit / S * 100,
        "cotation": "% du nominal" if in_pct else "% du spot",
        "delta": float(g["delta"]),  # par point d'indice (variation de valeur pour +1 point)
        "delta_cash_1pct": float(g["delta"]) * S * 0.01,  # P&L pour +1 % de spot
        "gamma_cash_1pct": float(g["gamma"]) * (S * 0.01) ** 2 / 2,  # terme de 2nd ordre pour 1 %
        "vega_1pt": float(g["vega"]),  # P&L pour +1 point de vol
        "devise": ins.ccy,
    }


def spot_vol_grid(
    spec, md, spot_shocks=(-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2), vol_shocks=(-0.05, 0.0, 0.05, 0.1)
):
    """P&L en full revaluation sur une grille choc de spot (relatif) x choc de vol (absolu)."""
    ins = build(spec)
    u = ins.underlying
    v0 = float(ins.value(md))
    rows = {}
    for dv in vol_shocks:
        rows[f"vol {dv * 100:+.0f} pts"] = [
            float(ins.value(md.bumped_spot(u, ds).bumped_vol(u, dv) if dv else md.bumped_spot(u, ds))) - v0
            for ds in spot_shocks
        ]
    return pd.DataFrame(rows, index=[f"spot {ds:+.0%}" for ds in spot_shocks]).T


def payoff_curve(spec, md, n=121, width=0.5):
    """Payoff à maturité (en valeur, notionnel inclus) sur [S(1-width), S(1+width)]."""
    ins = build(spec)
    S = md.spot(ins.underlying)
    grid = np.linspace(S * (1 - width), S * (1 + width), n)
    return pd.DataFrame({"spot_final": grid, "payoff": ins.notional * ins.payoff(grid)})


def stress_table(positions, md, scenarios):
    """Grille scénarios x positions (P&L EUR, full revaluation) avec une colonne TOTAL."""
    from quantlab.risk.engine import run_stress

    res = run_stress(positions, md, scenarios)
    grid = res.pivot_table(index="scenario", columns="position", values="pnl", aggfunc="sum")
    grid = grid.reindex([s.name for s in scenarios])
    grid["TOTAL"] = grid.sum(axis=1)
    return grid


def sma_sharpe_grid(prices, fasts, slows, start, end, cost_bps=5.0):
    """Sharpe des croisements de moyennes mobiles sur [start, end], en tableau fast x slow."""
    from quantlab.backtest.strategy import SMACross
    from quantlab.backtest.walkforward import grid_search

    res = grid_search(prices, SMACross, {"fast": list(fasts), "slow": list(slows)}, start, end, cost_bps)
    return res.pivot(index="fast", columns="slow", values="sharpe")


def equity_curves(prices, fast, slow, cost_bps=5.0):
    """Valeur de 1 investi : stratégie MM fast/slow contre achat et conservation."""
    from quantlab.backtest.engine import run_backtest
    from quantlab.backtest.strategy import BuyAndHold, SMACross

    strat = run_backtest(prices, SMACross(fast, slow).signal(prices), cost_bps)
    bench = run_backtest(prices, BuyAndHold().signal(prices), cost_bps)
    return pd.DataFrame({f"MM {fast}/{slow}": strat["equity"], "Achat et conservation": bench["equity"]})


def to_excel_bytes(sheets):
    """Classeur Excel en mémoire : {nom d'onglet: DataFrame} -> bytes (pour un bouton de téléchargement)."""
    from io import BytesIO

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31])  # Excel limite les noms d'onglet à 31 caractères
    return buf.getvalue()
