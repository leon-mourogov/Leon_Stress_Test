"""implied.py — volatilité implicite par recherche de racine."""

import numpy as np
from scipy.optimize import brentq

from quantlab.errors import PricingError
from quantlab.pricing.bs import bs_price


class ImpliedVolError(PricingError, ValueError):
    """Pas de volatilité compatible avec le prix donné."""


def implied_vol(price, S, K, T, r, q=0.0, call=True, low=1e-4, high=5.0, tol=1e-10):
    disc_S, disc_K = S * np.exp(-q * T), K * np.exp(-r * T)
    lower = max(disc_S - disc_K, 0.0) if call else max(disc_K - disc_S, 0.0)  # valeur intrinsèque actualisée
    upper = disc_S if call else disc_K
    if not lower < price < upper:
        raise ImpliedVolError(f"Prix {price:.6f} hors des bornes d'arbitrage ]{lower:.6f} ; {upper:.6f}[")

    def f(sigma):
        return bs_price(S, K, T, r, sigma, q, call) - price

    if f(low) > 0 or f(high) < 0:
        raise ImpliedVolError(f"Aucune vol entre {low} et {high} ne reproduit le prix {price:.6f}")
    return brentq(f, low, high, xtol=tol)
