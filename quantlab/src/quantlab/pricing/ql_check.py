"""ql_check.py — prix de référence QuantLib pour valider le pricer maison."""

import QuantLib as ql


def _process(S, r, q, sigma, today, dc):
    spot = ql.QuoteHandle(ql.SimpleQuote(S))
    rate = ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc, ql.Continuous))
    div = ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc, ql.Continuous))
    vol = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), sigma, dc))
    return ql.BlackScholesMertonProcess(spot, div, rate, vol)


def _setup(T_days):
    today = ql.Date(16, 10, 2026)
    ql.Settings.instance().evaluationDate = today
    dc = ql.Actual365Fixed()
    return today, today + T_days, dc


def ql_european(S, K, T_days, r, sigma, q=0.0, call=True):
    today, maturity, dc = _setup(T_days)
    payoff = ql.PlainVanillaPayoff(ql.Option.Call if call else ql.Option.Put, K)
    option = ql.VanillaOption(payoff, ql.EuropeanExercise(maturity))
    option.setPricingEngine(ql.AnalyticEuropeanEngine(_process(S, r, q, sigma, today, dc)))
    return {
        "price": option.NPV(),
        "delta": option.delta(),
        "gamma": option.gamma(),
        "vega": option.vega() / 100,
        "theta": option.thetaPerDay(),
        "rho": option.rho() / 100,
    }


def ql_digital(S, K, T_days, r, sigma, q=0.0, call=True, cash=1.0):
    today, maturity, dc = _setup(T_days)
    payoff = ql.CashOrNothingPayoff(ql.Option.Call if call else ql.Option.Put, K, cash)
    option = ql.VanillaOption(payoff, ql.EuropeanExercise(maturity))
    option.setPricingEngine(ql.AnalyticEuropeanEngine(_process(S, r, q, sigma, today, dc)))
    return option.NPV()


def ql_up_and_out_call(S, K, H, T_days, r, sigma, q=0.0):
    """Barrière surveillée en continu (formule fermée)."""
    today, maturity, dc = _setup(T_days)
    payoff = ql.PlainVanillaPayoff(ql.Option.Call, K)
    option = ql.BarrierOption(ql.Barrier.UpOut, H, 0.0, payoff, ql.EuropeanExercise(maturity))
    option.setPricingEngine(ql.AnalyticBarrierEngine(_process(S, r, q, sigma, today, dc)))
    return option.NPV()
