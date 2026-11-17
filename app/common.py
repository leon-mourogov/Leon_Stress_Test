"""common.py — ressources partagées par les pages : configuration, base, book, prix (aucun calcul)."""

import os
from pathlib import Path

import streamlit as st

from quantlab.config import load_settings
from quantlab.market.importer import load_price_files
from quantlab.risk.engine import load_book
from quantlab.risk.library import load_scenarios
from quantlab.storage import get_engine

ROOT = Path(__file__).resolve().parents[1]  # racine du dépôt, quel que soit le dossier de lancement


@st.cache_resource
def settings():
    # par défaut la démo (données versionnées : marche sur tout clone, en CI et en ligne) ;
    # avec vos propres données : QUANTLAB_SETTINGS=config/settings.yaml streamlit run app/Pricer.py
    return load_settings(ROOT / (os.environ.get("QUANTLAB_SETTINGS") or "config/settings_demo.yaml"))


@st.cache_resource
def engine():
    return get_engine(settings().database.url)  # une seule connexion partagée


@st.cache_data
def configured_prices():
    prices, _ = load_price_files(settings().paths.prices)
    return prices


def prices():
    """Prix importés dans la page « Import » s'il y en a, sinon ceux de la configuration."""
    imported = st.session_state.get("imported_prices")
    return imported if imported is not None else configured_prices()


def book():
    return load_book(settings().paths.book)  # rapide : pas de cache (les objets ne se hachent pas)


def scenario_library():
    return load_scenarios(settings().paths.scenarios)
