"""Heartbeat : il doit alerter quand le rapport du matin manque ou a échoué, et se taire sinon."""

from datetime import date, datetime

import pytest
from test_failures import write_config

from quantlab.pipelines import watchdog
from quantlab.storage import get_engine, log_run

MONDAY = date(2026, 1, 5)  # le rapport attendu est celui du vendredi 2 janvier
FRIDAY = date(2026, 1, 2)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    config, url = write_config(tmp_path)
    sent = []
    monkeypatch.setattr(watchdog, "send_alert", lambda cfg, subject, body: sent.append(body))
    return config, get_engine(url), sent


def test_silent_when_report_ok(setup):
    config, engine, sent = setup
    log_run(engine, FRIDAY, datetime(2026, 1, 2, 7, 30), "OK", 41.0, 0, "")
    assert watchdog.main(config, today=MONDAY) == 0 and sent == []


def test_alert_when_pipeline_never_started(setup):
    config, engine, sent = setup
    log_run(engine, date(2025, 12, 31), datetime(2025, 12, 31, 7, 30), "OK", 40.0, 0, "")
    assert watchdog.main(config, today=MONDAY) == 2
    assert "2026-01-02" in sent[0] and "pas démarré" in sent[0]


def test_alert_when_report_failed(setup):
    config, engine, sent = setup
    log_run(engine, FRIDAY, datetime(2026, 1, 2, 7, 30), "FAILED", 3.0, 0, "ConfigError: book vide")
    assert watchdog.main(config, today=MONDAY) == 2
    assert "FAILED" in sent[0] and "book vide" in sent[0]


def test_alert_on_empty_database(setup):
    config, _, sent = setup
    assert watchdog.main(config, today=MONDAY) == 2
    assert "jamais tourné" in sent[0]


def test_unreadable_config():
    assert watchdog.main("absent.yaml") == 2
