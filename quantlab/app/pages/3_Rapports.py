"""Rapports — historique des exécutions du pipeline et téléchargement des rapports."""

import streamlit as st
from common import engine, settings

from quantlab.storage import last_runs, metric_history

st.set_page_config(page_title="quantlab — Rapports", layout="wide")
st.title("Rapports quotidiens")

runs = last_runs(engine(), n=50)
if runs.empty:
    st.info(
        "Aucun rapport en base : lancez `python -m quantlab.pipelines.run_daily --config "
        "config/settings_demo.yaml --date 2025-12-31`, ou un rapport depuis la page Import."
    )
    st.stop()

ok = runs[runs["status"] == "OK"]
c1, c2, c3 = st.columns(3)
c1.metric("Dernier rapport OK", str(ok["as_of"].max()) if not ok.empty else "aucun")
c2.metric("Exécutions en base", len(runs))
c3.metric("Échecs ou partiels", int((runs["status"] != "OK").sum()))

st.subheader("VaR 99 % 1 jour (30 derniers rapports)")
var = metric_history(engine(), "var99", runs["as_of"].max(), days=30)
st.line_chart(var)

st.subheader("Journal des exécutions")
st.dataframe(runs[["as_of", "status", "duration_s", "n_warnings", "message"]], hide_index=True)

st.subheader("Télécharger un rapport")
day = st.selectbox("Date", sorted(ok["as_of"].unique(), reverse=True))
folder = settings().paths.reports / day.isoformat()
for f in sorted(folder.glob("risk_report_*")):
    st.download_button(f"Télécharger {f.name}", f.read_bytes(), file_name=f.name, key=f.name)
