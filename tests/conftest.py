"""conftest.py — fixtures partagées par tous les fichiers de tests."""

from pathlib import Path

import pytest

from quantlab.market.importer import load_price_files
from quantlab.market.samples import sample_market
from quantlab.risk.engine import load_book

ROOT = Path(__file__).resolve().parents[1]  # racine du projet, quel que soit le dossier courant
DATA = Path(__file__).resolve().parent / "data"  # données de test FIGÉES, versionnées avec les tests


@pytest.fixture
def md():
    """Marché de référence (immuable : on peut le partager sans risque)."""
    return sample_market()


@pytest.fixture(scope="session")
def book():
    return load_book(ROOT / "config" / "book.json")


@pytest.fixture(scope="session")
def prices():
    prices, _ = load_price_files([DATA / "fx.csv", DATA / "spx.csv"])
    return prices


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        help="réécrit les fichiers de référence (après vérification !)",
    )


@pytest.fixture
def update_golden(request):
    return request.config.getoption("--update-golden")
