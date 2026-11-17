"""Tests d'intégration du pipeline quotidien, sur données figées et dossiers temporaires."""

import logging
from datetime import date

import pytest
import yaml
from conftest import DATA, ROOT

from quantlab.config import load_settings
from quantlab.pipelines import run_daily as rd
from quantlab.pipelines.cli import EXIT_FAILED, EXIT_OK, EXIT_PARTIAL
from quantlab.storage import get_engine, last_runs

pytestmark = pytest.mark.slow  # environ 30 s : pytest -m "not slow" pour la boucle rapide


@pytest.fixture
def settings(tmp_path):
    raw = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    cfg = ROOT / "config"
    raw["paths"] = {
        "book": str(cfg / "book.json"),
        "scenarios": str(cfg / "scenarios.json"),
        "limits": str(cfg / "limits.json"),
        "prices": [str(DATA / "fx.csv"), str(DATA / "spx.csv")],
        "reports": str(tmp_path / "reports"),
        "logs": str(tmp_path / "logs"),
    }
    raw["database"]["url"] = f"sqlite:///{tmp_path / 'test.db'}"
    raw["risk"].update(var_window_days=100, mc_paths_var=1000)  # rapide : on teste la mécanique
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_settings(tmp_path / "settings.yaml")


def test_full_run_produces_files_and_logs_run(settings):
    code, ctx = rd.run_daily(date(2025, 12, 31), settings)
    assert code == EXIT_OK
    assert (ctx.out_dir / "DONE").read_text() == "OK"
    assert ctx.data["stress"].loc["Krach actions", "TOTAL"] == pytest.approx(-485_467, abs=1)
    runs = last_runs(ctx.data["engine"])
    assert list(runs["status"]) == ["OK"]


def test_second_run_does_nothing(settings, caplog):
    rd.run_daily(date(2025, 12, 31), settings)
    with caplog.at_level(logging.INFO, logger="quantlab"):
        code, _ = rd.run_daily(date(2025, 12, 31), settings)
    assert code == EXIT_OK and "déjà produit" in caplog.text


def test_stale_history_gives_partial_report(settings):
    code, ctx = rd.run_daily(date(2026, 12, 1), settings)
    assert code == EXIT_PARTIAL
    assert "var" not in ctx.data and ctx.warnings[0].startswith("var :")


def test_resume_after_crash(settings, monkeypatch):
    def crash(ctx):
        raise RuntimeError("disque plein")

    steps = list(rd.STEPS)
    monkeypatch.setattr(rd, "STEPS", [s if s[0] != "report" else ("report", crash, True) for s in steps])
    code, _ = rd.run_daily(date(2025, 12, 31), settings)
    assert code == EXIT_FAILED

    calls = []

    def spy_stress(ctx):
        calls.append(1)
        rd.step_stress(ctx)

    monkeypatch.setattr(rd, "STEPS", [s if s[0] != "stress" else ("stress", spy_stress, True) for s in steps])
    code, _ = rd.run_daily(date(2025, 12, 31), settings)
    assert code == EXIT_OK and calls == []  # le stress n'a pas été recalculé


def test_missing_book_is_blocking(settings, tmp_path):
    settings.paths.book = tmp_path / "absent.json"
    code, ctx = rd.run_daily(date(2025, 12, 31), settings)
    assert code == EXIT_FAILED
    assert "ConfigError" in last_runs(ctx.data["engine"])["message"].iloc[0]


def test_excel_and_pdf_report(settings):
    from openpyxl import load_workbook

    code, ctx = rd.run_daily(date(2025, 12, 31), settings)
    wb = load_workbook(next(ctx.out_dir.glob("*.xlsx")))
    assert wb.sheetnames == ["Synthese", "Limites", "Positions", "Stress", "VaR_PnL"]
    assert wb["Synthese"]["B3"].value == "COMPLET"
    assert wb["Limites"]["D2"].number_format == "0.0%"
    assert wb["Stress"].freeze_panes == "B2"
    pdf = next(ctx.out_dir.glob("*.pdf")).read_bytes()
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 2


def test_report_on_any_price_file(settings, tmp_path):
    """« run_daily --prices fichier » : export Excel français, le rapport porte sur sa dernière date."""
    from quantlab.market.importer import load_price_files

    prices, _ = load_price_files(settings.paths.prices)
    export = prices.loc[:"2025-06-30"].rename(columns={"EURUSD": "EUR/USD", "SPX": "S&P 500"})
    lines = ["Date;" + ";".join(export.columns)]
    for d, row in export.iterrows():
        lines.append(f"{d:%d/%m/%Y};" + ";".join(f"{v:.4f}".replace(".", ",") for v in row))
    (tmp_path / "export.csv").write_text("\n".join(lines), encoding="cp1252")
    cfg = tmp_path / "settings.yaml"
    code = rd.main(["--config", str(cfg), "--prices", str(tmp_path / "export.csv"), "--log-level", "WARNING"])
    assert code == EXIT_OK
    runs = last_runs(get_engine(settings.database.url))
    assert str(runs["as_of"].iloc[0]) == "2025-06-30"
