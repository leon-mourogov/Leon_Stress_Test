"""explain.py — approximations par les Greeks et explication du P&L."""


def taylor_pnl(instrument, md, md_shocked):
    """Décompose le P&L d'un produit à un seul sous-jacent : delta, gamma, vega, résidu."""
    u = instrument.underlying
    g = instrument.greeks(md)
    dS = md_shocked.spot(u) - md.spot(u)
    dvol_pts = (md_shocked.vols[u] - md.vols[u]) * 100  # vega est donnée par point de vol
    full = instrument.value(md_shocked) - instrument.value(md)
    parts = {
        "delta": g["delta"] * dS,
        "gamma": 0.5 * g["gamma"] * dS**2,
        "vega": g["vega"] * dvol_pts,
    }
    parts["residu"] = full - sum(parts.values())
    parts["full"] = full
    return {k: float(v) for k, v in parts.items()}
