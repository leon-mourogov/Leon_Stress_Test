"""bs.py — Black-Scholes-Merton : prix et Greeks analytiques (vectorisés)."""

import numpy as np
from scipy.stats import norm


def _d1_d2(S, K, T, r, q, sigma):
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    return d1, d1 - sigma * sqrt_T


def bs_price(S, K, T, r, sigma, q=0.0, call=True):
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    if call:
        return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)


def bs_greeks(S, K, T, r, sigma, q=0.0, call=True):
    """Greeks analytiques. vega par point de vol (0.01), theta par jour (/365), rho par 1 % (0.01)."""
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    dq, dr, pdf = np.exp(-q * T), np.exp(-r * T), norm.pdf(d1)
    sign = 1.0 if call else -1.0
    delta = sign * dq * norm.cdf(sign * d1)
    gamma = dq * pdf / (S * sigma * np.sqrt(T))
    vega = S * dq * pdf * np.sqrt(T) / 100
    theta = (
        -S * dq * pdf * sigma / (2 * np.sqrt(T))
        - sign * r * K * dr * norm.cdf(sign * d2)
        + sign * q * S * dq * norm.cdf(sign * d1)
    ) / 365
    rho = sign * K * T * dr * norm.cdf(sign * d2) / 100
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}
