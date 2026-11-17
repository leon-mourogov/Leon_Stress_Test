"""Comparer — deux produits côte à côte, sur le même marché."""

import pandas as pd
import streamlit as st

from quantlab.services import make_market, price

st.set_page_config(page_title="quantlab — Comparer", layout="wide")
st.title("Comparer deux produits")
mkt = make_market()
results = {}
for i, col in enumerate(st.columns(2)):
    with col:
        K = st.number_input("Strike", value=[5000.0, 4500.0][i], step=50.0, key=f"K{i}")
        T = st.slider("Maturité", 0.25, 5.0, 1.0, 0.25, key=f"T{i}")
        call = st.radio("Sens", ["Call", "Put"], index=i, key=f"cp{i}", horizontal=True) == "Call"
        spec = {"type": "european", "underlying": "SX5E", "K": K, "T": T, "call": call, "notional": 100}
        results[f"Produit {i + 1}"] = price(spec, mkt)
table = pd.DataFrame(results).drop(index=["devise", "cotation"]).astype(float).round(2)
st.dataframe(table)
