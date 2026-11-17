"""Tests de l'interface : l'app démarre, chaque page s'affiche sans exception, les widgets agissent."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path(__file__).resolve().parents[1] / "app" / "Pricer.py")
pytestmark = pytest.mark.slow  # quelques secondes : exclus de la boucle rapide (pytest -m "not slow")


def app():
    return AppTest.from_file(MAIN, default_timeout=60)


def test_pricer_default_values():
    at = app().run()
    assert not at.exception
    assert at.metric[0].label == "Valeur (EUR)"
    assert at.metric[0].value == "55 636"


def test_pricer_vol_slider_changes_price():
    at = app().run()
    vol = [s for s in at.sidebar.slider if s.label == "Volatilité (%)"][0]
    vol.set_value(23.0).run()
    assert at.metric[0].value == "74 584"


def test_basket_survives_reruns():
    at = app().run()
    for _ in range(3):
        at.button[0].click().run()
    assert len(at.session_state.basket) == 3


@pytest.mark.parametrize(
    "page",
    [
        "pages/0_Import.py",
        "pages/1_Stress.py",
        "pages/2_Backtest.py",
        "pages/3_Rapports.py",
        "pages/4_Comparer.py",
    ],
)
def test_page_renders(page):
    at = app().run()
    at.switch_page(page).run()
    assert not at.exception, at.exception


def test_stress_worst_scenario():
    at = app().run()
    at.switch_page("pages/1_Stress.py").run()
    assert at.metric[0].value == "Fuite vers le dollar"
    assert at.metric[1].value == "-268 897 EUR"


def test_autocall_in_pricer():
    at = app().run()
    at.sidebar.selectbox[0].set_value("Autocall")
    [s for s in at.sidebar.slider if s.label == "Maturité (années)"][0].set_value(5.0)
    at.run()
    assert not at.exception
    assert at.metric[0].value == "955 695"
