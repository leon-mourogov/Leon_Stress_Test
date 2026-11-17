"""instruments.py — produits financiers : une classe par produit, une seule interface."""

from abc import ABC, abstractmethod

import numpy as np
from scipy.stats import norm

from quantlab.pricing.bs import bs_greeks, bs_price


class Instrument(ABC):
    """Tout produit sait se valoriser sur un MarketData. Montants dans la devise `ccy`."""

    def __init__(self, notional=1.0, ccy="EUR"):
        self.notional = notional
        self.ccy = ccy

    @abstractmethod
    def unit_price(self, md):
        """Prix pour 1 unité de notionnel."""

    def value(self, md):
        return self.notional * self.unit_price(md)

    def greeks(self, md, rel_bump=0.01, vol_bump=0.01):
        """Greeks par différences finies, valables pour TOUT produit (sous-jacent `underlying`)."""
        u = self.underlying
        h = md.spot(u) * rel_bump
        v0 = self.value(md)
        up, dn = self.value(md.bumped_spot(u, rel_bump)), self.value(md.bumped_spot(u, -rel_bump))
        vega = (self.value(md.bumped_vol(u, vol_bump)) - self.value(md.bumped_vol(u, -vol_bump))) / 2
        return {"delta": (up - dn) / (2 * h), "gamma": (up - 2 * v0 + dn) / h**2, "vega": vega}

    def payoff(self, ST):
        """Flux à maturité pour 1 unité de notionnel, en fonction du spot final (tableau NumPy)."""
        raise NotImplementedError(f"{type(self).__name__} : payoff non défini")

    def __repr__(self):
        fields = ", ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{type(self).__name__}({fields})"


class Forward(Instrument):
    """Achat à terme de `underlying` au prix K. Valeur = S e^{-qT} - K e^{-rT}."""

    def __init__(self, underlying, K, T, notional=1.0, ccy="EUR"):
        super().__init__(notional, ccy)
        self.underlying, self.K, self.T = underlying, K, T

    def unit_price(self, md):
        S, r = md.spot(self.underlying), md.curves[self.ccy].rate(self.T)
        q = md.div_yields.get(self.underlying, 0.0)
        return S * np.exp(-q * self.T) - self.K * np.exp(-r * self.T)

    def payoff(self, ST):
        return np.asarray(ST, dtype=float) - self.K


class EuropeanOption(Instrument):
    def __init__(self, underlying, K, T, call=True, notional=1.0, ccy="EUR"):
        super().__init__(notional, ccy)
        if K <= 0 or T <= 0:
            raise ValueError(f"Strike et maturité doivent être > 0 (K={K}, T={T})")
        self.underlying, self.K, self.T, self.call = underlying, K, T, call

    def _inputs(self, md):
        return (
            md.spot(self.underlying),
            self.K,
            self.T,
            md.curves[self.ccy].rate(self.T),
            md.vols[self.underlying],
            md.div_yields.get(self.underlying, 0.0),
        )

    def unit_price(self, md):
        S, K, T, r, sigma, q = self._inputs(md)
        return bs_price(S, K, T, r, sigma, q, self.call)

    def greeks(self, md, **kwargs):
        """Surcharge : formules fermées, plus précises et plus rapides que les différences finies."""
        S, K, T, r, sigma, q = self._inputs(md)
        g = bs_greeks(S, K, T, r, sigma, q, self.call)
        return {k: self.notional * float(g[k]) for k in ("delta", "gamma", "vega")}

    def payoff(self, ST):
        ST = np.asarray(ST, dtype=float)
        return np.maximum(ST - self.K, 0.0) if self.call else np.maximum(self.K - ST, 0.0)


class DigitalOption(Instrument):
    """Cash-or-nothing : paie 1 (× notionnel) si S_T > K pour un call, S_T < K pour un put."""

    def __init__(self, underlying, K, T, call=True, notional=1.0, ccy="EUR"):
        super().__init__(notional, ccy)
        self.underlying, self.K, self.T, self.call = underlying, K, T, call

    def unit_price(self, md):
        S, r = md.spot(self.underlying), md.curves[self.ccy].rate(self.T)
        sigma, q = md.vols[self.underlying], md.div_yields.get(self.underlying, 0.0)
        d2 = (np.log(S / self.K) + (r - q - 0.5 * sigma**2) * self.T) / (sigma * np.sqrt(self.T))
        return np.exp(-r * self.T) * norm.cdf(d2 if self.call else -d2)

    def payoff(self, ST):
        ST = np.asarray(ST, dtype=float)
        return (ST > self.K).astype(float) if self.call else (ST < self.K).astype(float)


class FXOption(EuropeanOption):
    """Garman-Kohlhagen : BS où le taux de la devise de base joue le rôle du dividende.

    underlying = "EURUSD" ; ccy = devise de cotation (USD) ; prime en USD pour 1 EUR de notionnel.
    """

    def _inputs(self, md):
        base, quote = self.underlying[:3], self.underlying[3:]
        if self.ccy != quote:
            raise ValueError(f"Prime en {quote} attendue pour {self.underlying}, reçu {self.ccy}")
        return (
            md.spot(self.underlying),
            self.K,
            self.T,
            md.curves[quote].rate(self.T),
            md.vols[self.underlying],
            md.curves[base].rate(self.T),
        )


class BarrierOption(Instrument):
    """Call up-and-out, barrière observée à chaque pas (`n_obs` par an), Monte Carlo."""

    def __init__(self, underlying, K, H, T, notional=1.0, ccy="EUR", n_obs=252, n_paths=100_000, seed=42):
        super().__init__(notional, ccy)
        if H <= K:
            raise ValueError("Up-and-out call : la barrière doit être au-dessus du strike")
        self.underlying, self.K, self.H, self.T = underlying, K, H, T
        self.n_obs, self.n_paths, self.seed = n_obs, n_paths, seed

    def unit_price(self, md):
        S, r = md.spot(self.underlying), md.curves[self.ccy].rate(self.T)
        sigma, q = md.vols[self.underlying], md.div_yields.get(self.underlying, 0.0)
        n_steps = max(1, round(self.n_obs * self.T))
        dt = self.T / n_steps
        z = np.random.default_rng(self.seed).standard_normal((self.n_paths, n_steps))
        paths = S * np.exp(np.cumsum((r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z, axis=1))
        alive = paths.max(axis=1) < self.H
        return np.exp(-r * self.T) * np.mean(np.maximum(paths[:, -1] - self.K, 0) * alive)

    def payoff(self, ST):
        """Payoff à maturité SI la barrière n'a jamais été touchée (il dépend du chemin)."""
        ST = np.asarray(ST, dtype=float)
        return np.where(ST < self.H, np.maximum(ST - self.K, 0.0), 0.0)


class CapitalProtectedNote(Instrument):
    """Note : rembourse 100 % du nominal + participation × max(S_T/S_0 - 1, 0)."""

    def __init__(self, underlying, T, participation, S0, notional=1.0, ccy="EUR"):
        super().__init__(notional, ccy)
        self.underlying, self.T, self.participation, self.S0 = underlying, T, participation, S0

    def components(self, md):
        zero_coupon = float(md.curves[self.ccy].discount(self.T))
        call = EuropeanOption(self.underlying, self.S0, self.T, ccy=self.ccy).unit_price(md) / self.S0
        return zero_coupon, float(call)

    def unit_price(self, md):
        zc, call = self.components(md)
        return zc + self.participation * call

    def fair_participation(self, md, issue_price=1.0, margin=0.0):
        """Participation qui rend la note égale à son prix d'émission, net de la marge."""
        zc, call = self.components(md)
        return (issue_price - margin - zc) / call

    def payoff(self, ST):
        ST = np.asarray(ST, dtype=float)
        return 1.0 + self.participation * np.maximum(ST / self.S0 - 1.0, 0.0)


class Autocall(Instrument):
    """Autocall : rappel anticipé avec coupon cumulé si S_t >= rappel x S0 à une date d'observation ;
    à maturité, capital protégé si S_T >= protection x S0, sinon perte de S_T / S0. Monte Carlo."""

    def __init__(
        self,
        underlying,
        T,
        S0,
        coupon,
        autocall=1.0,
        protection=0.6,
        obs_per_year=1,
        notional=1.0,
        ccy="EUR",
        n_paths=100_000,
        seed=42,
    ):
        super().__init__(notional, ccy)
        if not 0 <= protection <= autocall:
            raise ValueError("Il faut 0 <= protection <= niveau de rappel")
        self.underlying, self.T, self.S0, self.coupon = underlying, T, S0, coupon
        self.autocall, self.protection, self.obs_per_year = autocall, protection, obs_per_year
        self.n_paths, self.seed = n_paths, seed

    def obs_dates(self):
        n = max(1, round(self.T * self.obs_per_year))
        return np.linspace(self.T / n, self.T, n)

    def simulate(self, md):
        """Performances S_t / S0 aux dates d'observation : tableau (n_paths, n_dates)."""
        S, r = md.spot(self.underlying), md.curves[self.ccy].rate(self.T)
        sigma, q = md.vols[self.underlying], md.div_yields.get(self.underlying, 0.0)
        t = self.obs_dates()
        dt = np.diff(t, prepend=0.0)
        z = np.random.default_rng(self.seed).standard_normal((self.n_paths, len(t)))
        log_ret = np.cumsum((r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z, axis=1)
        return S / self.S0 * np.exp(log_ret), t, r

    def cashflows(self, md):
        """(montant, date de paiement) de chaque chemin, pour 1 de nominal."""
        perf, t, r = self.simulate(md)
        called = perf >= self.autocall
        called[:, -1] = False  # à maturité, la règle finale s'applique
        any_call = called.any(axis=1)
        first = np.where(any_call, called.argmax(axis=1), len(t) - 1)
        final = perf[:, -1]
        at_maturity = np.where(
            final >= self.autocall, 1 + self.coupon * t[-1], np.where(final >= self.protection, 1.0, final)
        )
        amount = np.where(any_call, 1 + self.coupon * t[first], at_maturity)
        return amount, t[first], r

    def unit_price(self, md):
        amount, when, r = self.cashflows(md)
        return float(np.mean(amount * np.exp(-r * when)))

    def scenarios(self, md):
        """Probabilités risque neutre de chaque issue : rappel à chaque date, ou sort à maturité."""
        amount, when, _ = self.cashflows(md)
        t = self.obs_dates()
        out = {f"rappel en {ti:g} an(s)": float(np.mean((when == ti) & (amount > 1))) for ti in t}
        out["capital rendu sans coupon"] = float(np.mean(amount == 1.0))
        out["perte en capital"] = float(np.mean(amount < 1.0))
        return out

    def payoff(self, ST):
        """Flux à maturité SI le produit n'a pas été rappelé avant (il dépend du chemin)."""
        x = np.asarray(ST, dtype=float) / self.S0
        return np.where(x >= self.autocall, 1 + self.coupon * self.T, np.where(x >= self.protection, 1.0, x))


PRODUCTS = {
    "forward": Forward,
    "european": EuropeanOption,
    "digital": DigitalOption,
    "fx_option": FXOption,
    "barrier": BarrierOption,
    "cpn": CapitalProtectedNote,
    "autocall": Autocall,
}


def build(spec: dict) -> Instrument:
    """Factory : {"type": "european", "underlying": ..., ...} -> objet Instrument."""
    spec = dict(spec)
    kind = spec.pop("type")
    if kind not in PRODUCTS:
        raise ValueError(f"Produit inconnu : {kind!r}. Connus : {sorted(PRODUCTS)}")
    return PRODUCTS[kind](**spec)
