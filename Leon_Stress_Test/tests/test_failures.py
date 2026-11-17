"""Pannes simulées : bon code de sortie, statut en base, alerte qui donne la cause."""

import pytest
import yaml
from conftest import DATA, ROOT

from quantlab.errors import MarketDataError
from quantlab.pipelines import run_daily as rd
from quantlab.pipelines.cli import EXIT_FAILED, EXIT_PARTIAL
from quantlab.storage import get_engine, last_runs

pytestmark = pytest.mark.slow
AS_OF = "2025-12-31"


def write_config(tmp_path, book=None, spots=None):
    """Configuration de test dans tmp_path ; `book` remplace le contenu de book.json."""
    raw = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    cfg = ROOT / "config"
    book_path = cfg / "book.json"
    if book is not None:
        book_path = tmp_path / "book.json"
        book_path.write_text(book, encoding="utf-8")
    raw["paths"] = {
        "book": str(book_path),
        "scenarios": str(cfg / "scenarios.json"),
        "limits": str(cfg / "limits.json"),
        "prices": [str(DATA / "fx.csv"), str(DATA / "spx.csv")],
        "reports": str(tmp_path / "reports"),
        "logs": str(tmp_path / "logs"),
    }
    raw["database"]["url"] = f"sqlite:///{tmp_path / 'test.db'}"
    raw["risk"].update(var_window_days=100, mc_paths_var=1000)
    if spots is not None:
        raw["market"]["spots"] = spots
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path, raw["database"]["url"]


@pytest.fixture
def alerts(monkeypatch):
    """Remplace l'envoi de mail : on capture (sujet, corps)."""
    sent = []
    monkeypatch.setattr(rd, "send_alert", lambda cfg, subject, body: sent.append((subject, body)))
    return sent


def source_down(monkeypatch):
    def fail(*args, **kwargs):  # ce que lève MarketDataLoader après 3 réponses 500 (test_loader.py)
        raise MarketDataError("Source indisponible après 3 tentatives : https://data-api.ecb.europa.eu/...")

    monkeypatch.setattr(rd, "load_price_files", fail)


# cas : (configuration, sabotage, code attendu, statut en base, mot attendu dans l'alerte)
CASES = {
    "api_500": (dict(), source_down, EXIT_PARTIAL, "PARTIAL", "Source indisponible"),
    "json_corrompu": (
        dict(book='[{"id": "T1", "type": "european",'),
        None,
        EXIT_FAILED,
        "FAILED",
        "JSON invalide",
    ),
    "spot_manquant": (dict(spots={"EURUSD": 1.17}), None, EXIT_FAILED, "FAILED", "SX5E (positions T1"),
    "book_vide": (dict(book="[]"), None, EXIT_FAILED, "FAILED", "book vide"),
}


@pytest.mark.parametrize("case", CASES)
def test_simulated_failure(case, tmp_path, monkeypatch, alerts):
    config_kwargs, sabotage, expected_code, expected_status, expected = CASES[case]
    config, db_url = write_config(tmp_path, **config_kwargs)
    if sabotage:
        sabotage(monkeypatch)
    code = rd.main(["--config", str(config), "--date", AS_OF])
    assert code == expected_code
    runs = last_runs(get_engine(db_url))
    assert list(runs["status"]) == [expected_status]
    assert expected in runs["message"].iloc[0]
    subject, body = alerts[0]
    assert ("ÉCHEC" if expected_code == EXIT_FAILED else "INCOMPLET") in subject
    assert expected in body  # l'alerte dit QUOI réparer, pas seulement « échec »
