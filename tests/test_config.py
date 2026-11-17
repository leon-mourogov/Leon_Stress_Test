"""Configuration YAML et ligne de commande."""

from datetime import date

import pytest
from conftest import ROOT

from quantlab.config import load_settings
from quantlab.errors import ConfigError
from quantlab.pipelines.cli import parse_args, previous_business_day


def test_settings_paths_are_relative_to_config_file():
    s = load_settings(ROOT / "config" / "settings.yaml")
    assert s.paths.book == ROOT / "config" / "book.json"
    assert s.paths.prices == [ROOT / "data" / "fx.csv", ROOT / "data" / "spx.csv"]
    assert s.database.url == f"sqlite:///{ROOT / 'quantlab.db'}"


def test_vol_in_percent_is_rejected(tmp_path):
    text = (ROOT / "config" / "settings.yaml").read_text(encoding="utf-8").replace("SX5E: 0.18", "SX5E: 18")
    (tmp_path / "s.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="décimal"):
        load_settings(tmp_path / "s.yaml")


def test_missing_file():
    with pytest.raises(ConfigError, match="introuvable"):
        load_settings("absent.yaml")


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 10, 27), date(2026, 10, 26)),  # mardi -> lundi
        (date(2026, 10, 26), date(2026, 10, 23)),  # lundi -> vendredi
        (date(2026, 11, 1), date(2026, 10, 30)),
    ],  # dimanche -> vendredi
)
def test_previous_business_day(today, expected):
    assert previous_business_day(today) == expected


def test_cli_parses_date():
    args = parse_args(["--date", "2026-12-01", "--log-level", "DEBUG"])
    assert args.date == date(2026, 12, 1) and args.log_level == "DEBUG"


def test_cli_rejects_bad_date():
    with pytest.raises(SystemExit) as exc:
        parse_args(["--date", "01/12/2026"])
    assert exc.value.code == 2


def test_book_errors_are_config_errors(tmp_path):
    from quantlab.risk.engine import load_book

    with pytest.raises(ConfigError, match="introuvable"):
        load_book(tmp_path / "absent.json")
    (tmp_path / "b.json").write_text('[{"id": "X1", "type": "swaption"}]')
    with pytest.raises(ConfigError, match="trade n°1.*swaption"):
        load_book(tmp_path / "b.json")
    (tmp_path / "c.json").write_text('[{"id": "X1", "type": "european",}]')
    with pytest.raises(ConfigError, match="JSON invalide"):
        load_book(tmp_path / "c.json")
