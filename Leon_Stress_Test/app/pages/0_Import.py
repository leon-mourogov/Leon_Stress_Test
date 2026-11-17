"""Import — importer un fichier de prix (CSV ou Excel), voir ce qui a été compris, relancer le rapport."""

import tempfile
from pathlib import Path

import streamlit as st
from common import configured_prices, settings

from quantlab.errors import QuantLabError
from quantlab.market.importer import combine_prices, read_price_file
from quantlab.pipelines.run_daily import run_daily

st.set_page_config(page_title="quantlab — Import", layout="wide")
st.title("Import de données de marché")
st.write(
    "Importez un ou plusieurs fichiers de prix : CSV (séparateur et virgule décimale détectés) "
    "ou Excel (.xlsx), "
    "une colonne de dates et une colonne par série, ou le format long (date, série, valeur)."
)

uploads = st.file_uploader("Fichiers de prix", type=["csv", "txt", "xlsx"], accept_multiple_files=True)

if not uploads:
    data = st.session_state.get("imported_prices")
    source = "fichiers importés" if data is not None else "fichiers de la configuration"
    data = data if data is not None else configured_prices()
    st.info(
        f"Données utilisées par l'application : {source} — séries {', '.join(data.columns)}, "
        f"du {data.index[0]:%d/%m/%Y} au {data.index[-1]:%d/%m/%Y}."
    )
    if st.session_state.get("imported_prices") is not None and st.button(
        "Revenir aux données de la configuration"
    ):
        del st.session_state["imported_prices"]
        st.rerun()
    st.stop()

frames, reports = [], []
for f in uploads:
    try:
        df, rep = read_price_file(f.getvalue(), name=f.name)
    except QuantLabError as e:
        st.error(f"{f.name} : {e}")
        st.stop()
    frames.append(df)
    reports.append(rep)
try:
    data = combine_prices(frames)
except QuantLabError as e:
    st.error(str(e))
    st.stop()

st.subheader("Ce qui a été compris")
for rep in reports:
    st.code(rep.summary(), language=None)
st.metric(
    "Dates communes",
    f"{len(data)}",
    f"du {data.index[0]:%d/%m/%Y} au {data.index[-1]:%d/%m/%Y}",
    delta_color="off",
)
st.line_chart(data / data.bfill().iloc[0] * 100)  # base 100 : séries comparables
st.caption("Séries en base 100 à la première date.")

if st.button("Utiliser ces données dans l'application (pages Backtest...)"):
    st.session_state["imported_prices"] = data
    st.success("Données importées : les autres pages les utilisent jusqu'à la fin de la session.")

st.subheader("Rapport de risque complet sur ces données")
cfg = settings()
as_of = st.date_input(
    "Date du rapport",
    value=data.index[-1].date(),
    min_value=data.index[0].date(),
    max_value=data.index[-1].date(),
)

if st.button("Lancer le rapport", type="primary"):
    with st.spinner("Valorisation, stress, VaR, rapport Excel et PDF..."):
        work = Path(tempfile.mkdtemp(prefix="quantlab_"))
        files = []
        for f in uploads:
            path = work / f.name
            path.write_bytes(f.getvalue())
            files.append(path)
        s = cfg.model_copy(deep=True)
        s.paths.prices, s.paths.reports, s.paths.logs = files, work / "reports", work / "logs"
        s.database.url = f"sqlite:///{work / 'quantlab.db'}"
        code, ctx = run_daily(as_of, s, force=True)
    label = {0: "OK", 1: "INCOMPLET", 2: "ÉCHEC"}[code]
    (st.success if code == 0 else st.warning if code == 1 else st.error)(
        f"Rapport du {as_of:%d/%m/%Y} : {label}"
    )
    for w in ctx.warnings:
        st.warning(w)
    if ctx.error:
        st.error(ctx.error)
    if "metrics" in ctx.data:
        m = ctx.data["metrics"]
        c1, c2, c3 = st.columns(3)
        fmt = lambda x: f"{x:,.0f} EUR".replace(",", " ")  # noqa: E731
        c1.metric("VaR 99 % 1 jour", fmt(m["var99"]) if "var99" in m else "non calculée")
        c2.metric("ES 97,5 %", fmt(m["es975"]) if "es975" in m else "non calculée")
        c3.metric("Pire stress", fmt(-m["stress_worst"]))
        st.dataframe(ctx.data["stress"].style.format("{:,.0f}"), width="stretch")
    for path in ctx.data.get("files", []):
        st.download_button(
            f"Télécharger {Path(path).name}",
            Path(path).read_bytes(),
            file_name=Path(path).name,
            key=str(path),
        )
