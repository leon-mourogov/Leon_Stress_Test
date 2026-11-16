"""Backtest — grille de moyennes mobiles, carte des Sharpe et courbes de valeur."""

import streamlit as st
from common import prices

from quantlab.services import equity_curves, sma_sharpe_grid

st.set_page_config(page_title="quantlab — Backtest", layout="wide")
st.title("Backtest : croisement de moyennes mobiles")

FASTS, SLOWS = [5, 10, 20, 30, 50, 75, 100], [50, 100, 150, 200, 250, 300]

data = prices()
years = sorted(data.index.year.unique())
with st.sidebar:
    columns = list(data.columns)
    name = st.selectbox("Série", columns, index=columns.index("SPX") if "SPX" in columns else 0)
    default = (years[0], years[min(4, len(years) - 1)])
    start, end = st.select_slider("Période d'estimation", options=years, value=default)
    cost = st.slider("Coûts (bp par transaction)", 0, 50, 5)
series = data[name].dropna()


@st.cache_data(show_spinner="Grille de backtests...")
def cached_grid(series, start, end, cost):
    return sma_sharpe_grid(series, FASTS, SLOWS, f"{start}-01-01", f"{end}-12-31", cost)


grid = cached_grid(series, start, end, cost).astype(float)  # combinaisons fast >= slow : NaN
if grid.isna().all().all():
    st.warning("Période trop courte pour ces moyennes mobiles : élargissez la période d'estimation.")
    st.stop()
st.subheader(f"{name} — ratio de Sharpe {start}-{end} (lignes : MM courte, colonnes : MM longue)")
st.dataframe(
    grid.style.format("{:.2f}", na_rep="")
    .background_gradient(cmap="RdBu", axis=None, vmin=-1, vmax=1)
    .highlight_null(color="white"),
    width="stretch",
)
best = grid.stack().idxmax()
st.caption(
    f"Meilleure combinaison : MM {best[0]}/{best[1]} (Sharpe {grid.loc[best]:.2f}) sur {grid.count().sum()} "
    "essais. Le meilleur de N essais n'est pas un signal : comparez avec la période suivante."
)
c1, c2 = st.columns(2)
fast = c1.selectbox("MM courte", FASTS, index=FASTS.index(best[0]))
slow = c2.selectbox("MM longue", SLOWS, index=SLOWS.index(best[1]))
if fast < slow:
    st.line_chart(equity_curves(series, fast, slow, cost))
else:
    st.warning("La moyenne courte doit être plus courte que la longue.")
