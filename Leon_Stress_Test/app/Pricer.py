"""Pricer.py — page d'accueil de l'app : prix, Greeks, payoff et grille de stress d'un produit."""

import streamlit as st

from quantlab.services import make_market, payoff_curve, price, spot_vol_grid

st.set_page_config(page_title="quantlab — Pricer", layout="wide")


@st.cache_data(show_spinner="Valorisation...")
def cached_price(spec, mkt):
    return price(spec, make_market(**mkt))


@st.cache_data(show_spinner="Grille de stress (full revaluation)...")
def cached_grid(spec, mkt):
    return spot_vol_grid(spec, make_market(**mkt))


def product_inputs():
    """Widgets du produit -> dictionnaire spec (le même format que book.json)."""
    kind = st.selectbox(
        "Produit", ["Européenne", "Digitale", "Barrière up-and-out", "Note capital garanti", "Autocall"]
    )
    T = st.slider("Maturité (années)", 0.25, 5.0, 1.0, 0.25)
    if kind == "Note capital garanti":
        part = st.slider("Participation (%)", 10, 150, 60, 5) / 100
        notional = st.number_input("Nominal (EUR)", value=1_000_000, step=100_000)
        return {
            "type": "cpn",
            "underlying": "SX5E",
            "T": T,
            "participation": part,
            "S0": st.number_input("Niveau initial S0 (fixé à l'émission)", value=4900.0, step=10.0),
            "notional": notional,
        }
    if kind == "Autocall":
        return {
            "type": "autocall",
            "underlying": "SX5E",
            "T": T,
            "S0": st.number_input("Niveau initial S0 (fixé à l'émission)", value=4900.0, step=10.0),
            "coupon": st.slider("Coupon annuel (%)", 0.0, 20.0, 7.0, 0.25) / 100,
            "autocall": st.slider("Niveau de rappel (% de S0)", 50, 120, 100, 5) / 100,
            "protection": st.slider("Protection du capital (% de S0)", 0, 100, 60, 5) / 100,
            "notional": st.number_input("Nominal (EUR)", value=1_000_000, step=100_000),
        }
    K = st.number_input("Strike", value=5000.0, step=50.0)
    if kind == "Barrière up-and-out":
        H = st.number_input("Barrière", value=6125.0, step=50.0)
        return {
            "type": "barrier",
            "underlying": "SX5E",
            "K": K,
            "H": H,
            "T": T,
            "notional": st.number_input("Quantité", value=100, step=10),
        }
    call = st.radio("Sens", ["Call", "Put"], horizontal=True) == "Call"
    if kind == "Digitale":
        return {
            "type": "digital",
            "underlying": "SX5E",
            "K": K,
            "T": T,
            "call": call,
            "notional": st.number_input("Montant payé (EUR)", value=500_000, step=50_000),
        }
    return {
        "type": "european",
        "underlying": "SX5E",
        "K": K,
        "T": T,
        "call": call,
        "notional": st.number_input("Quantité", value=200, step=10),
    }


with st.sidebar:
    st.header("Produit")
    spec = product_inputs()
    st.header("Marché")
    mkt = {
        "spot": st.number_input("Spot SX5E", value=4900.0, step=10.0),
        "vol": st.slider("Volatilité (%)", 5.0, 80.0, 18.0, 0.5) / 100,
        "rate": st.number_input("Taux EUR (%)", value=2.0, step=0.25) / 100,
        "div": st.number_input("Dividende (%)", value=3.0, step=0.25) / 100,
    }

st.title("Pricer")
res = cached_price(spec, mkt)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Valeur (EUR)", f"{res['valeur']:,.0f}".replace(",", " "))
c2.metric(
    "Prix unitaire",
    f"{res['prix_unitaire']:.4g}",
    f"{res['prix_pct']:.2f} {res['cotation']}",
    delta_color="off",
)
c3.metric("Delta cash (+1 % spot)", f"{res['delta_cash_1pct']:,.0f}".replace(",", " "))
c4.metric("Vega (+1 pt de vol)", f"{res['vega_1pt']:,.0f}".replace(",", " "))

# panier de comparaison : survit aux réexécutions grâce à session_state
if "basket" not in st.session_state:
    st.session_state.basket = []
if st.button("Ajouter au panier de comparaison"):
    st.session_state.basket.append(
        {
            "produit": spec["type"],
            **{k: round(v, 2) for k, v in res.items() if k not in ("devise", "cotation")},
        }
    )

left, right = st.columns(2)
with left:
    st.subheader("Payoff à maturité")
    st.line_chart(payoff_curve(spec, make_market(**mkt)), x="spot_final", y="payoff")
with right:
    st.subheader("P&L en full revaluation (EUR)")
    if st.toggle("Calculer la grille spot x vol", value=True):
        grid = cached_grid(spec, mkt)
        st.dataframe(
            grid.style.format("{:,.0f}").background_gradient(
                cmap="RdBu", axis=None, vmin=-abs(grid).max().max(), vmax=abs(grid).max().max()
            )
        )

if st.session_state.basket:
    st.subheader(f"Panier de comparaison ({len(st.session_state.basket)} produits)")
    st.dataframe(st.session_state.basket)
