"""Stress — le book sous la bibliothèque de scénarios et un scénario composé à la main."""

import streamlit as st
from common import book, scenario_library

from quantlab.market.samples import sample_market
from quantlab.risk.scenario import BASE, Scenario
from quantlab.services import stress_table, to_excel_bytes

st.set_page_config(page_title="quantlab — Stress", layout="wide")
st.title("Stress test du book")


@st.cache_data(show_spinner="Revalorisation complète du book...")
def cached_stress(custom):
    scenarios = [BASE, *scenario_library()]
    if custom:
        scenarios.append(Scenario("Mon scénario", **custom))
    return stress_table(book(), sample_market(), scenarios)


with st.sidebar:
    st.header("Composer un scénario")
    use_custom = st.checkbox("Ajouter mon scénario", value=True)
    ds = st.slider("Choc SX5E (%)", -50, 30, -15, 1) / 100
    dv = st.slider("Choc vol SX5E (points)", -10, 40, 10, 1) / 100
    dfx = st.slider("Choc EURUSD (%)", -20, 20, 0, 1) / 100
    drate = st.slider("Choc taux EUR (bp)", -200, 200, 0, 25)

custom = None
if use_custom:
    custom = {
        "spot_shocks": {"SX5E": ds, "EURUSD": dfx},
        "vol_shocks": {"SX5E": dv},
        "curve_shocks": {"EUR": drate} if drate else {},
    }
grid = cached_stress(custom)
worst = grid["TOTAL"].idxmin()
c1, c2 = st.columns(2)
c1.metric(
    "Pire scénario", worst, f"{grid.loc[worst, 'TOTAL']:,.0f} EUR".replace(",", " "), delta_color="normal"
)
if custom:
    c2.metric("Mon scénario", f"{grid.loc['Mon scénario', 'TOTAL']:,.0f} EUR".replace(",", " "))
lim = float(abs(grid.drop(columns="TOTAL")).max().max())
st.dataframe(
    grid.style.format("{:,.0f}").background_gradient(cmap="RdBu", axis=None, vmin=-lim, vmax=lim),
    width="stretch",
)
st.caption("P&L en EUR, revalorisation complète de chaque position. Rouge : perte ; bleu : gain.")
st.download_button(
    "Exporter en Excel",
    data=to_excel_bytes({"Stress": grid}),
    file_name="stress_book.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
