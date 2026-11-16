import logging

from conftest import DATA

from quantlab.log import setup_logging
from quantlab.market.importer import read_price_file


def test_import_logs_cleaning(caplog):
    with caplog.at_level(logging.INFO, logger="quantlab"):
        read_price_file(DATA / "fx.csv")
    assert "1 doublon(s), 2 manquante(s), 1 erreur(s) de saisie" in caplog.text


def test_setup_logging_twice_does_not_duplicate_handlers(tmp_path):
    setup_logging(logfile=tmp_path / "a.log")
    root = setup_logging(logfile=tmp_path / "a.log")
    assert len(root.handlers) == 2  # console + fichier, pas 4
