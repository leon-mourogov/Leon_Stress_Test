"""Import de fichiers de prix : formats variés, nettoyage tracé, erreurs claires."""

import pandas as pd
import pytest
from conftest import DATA

from quantlab.errors import DataQualityError, MarketDataError
from quantlab.market.importer import canonical_name, combine_prices, load_price_files, read_price_file


@pytest.fixture(scope="module")
def reference():
    prices, _ = load_price_files([DATA / "fx.csv", DATA / "spx.csv"])
    return prices.loc["2024"]


def test_reference_files_are_cleaned_and_reported():
    prices, reports = load_price_files([DATA / "fx.csv", DATA / "spx.csv"])
    fx, spx = reports
    assert (fx.duplicates, sum(fx.missing.values()), sum(fx.typos.values())) == (1, 2, 1)
    assert spx.renamed == {"close": "SPX"}  # colonne générique : nom tiré du fichier
    assert list(prices.columns) == ["EURUSD", "USDJPY", "SPX"]
    assert prices.index.is_monotonic_increasing and not prices.isna().any().any()


def test_french_excel_export(tmp_path, reference):
    """Point-virgule, virgule décimale, espaces de milliers, JJ/MM/AAAA, Windows-1252, #N/A, pied de page."""
    lines = ["Date;EUR/USD;S&P 500;Commentaire"]
    for d, r in reference.iterrows():
        eur = f"{r.EURUSD:.4f}".replace(".", ",")
        spx = f"{r.SPX:,.2f}".replace(",", " ").replace(".", ",")
        lines.append(f"{d:%d/%m/%Y};{eur};{spx};clôture")
    lines[5] = lines[5].split(";")[0] + ";#N/A;" + lines[5].split(";")[2] + ";"
    lines.append("Source : export du terminal;;;")
    path = tmp_path / "export.csv"
    path.write_text("\n".join(lines), encoding="cp1252")

    prices, report = read_price_file(path)
    assert (report.separator, report.decimal, report.encoding) == (";", ",", "Windows-1252")
    assert report.date_format == "JJ/MM/AAAA"
    assert report.renamed == {"EUR/USD": "EURUSD", "S&P 500": "SPX"}
    assert report.dropped_columns == ["Commentaire"]
    assert report.missing == {"EURUSD": 1}
    pd.testing.assert_series_equal(prices["SPX"], reference["SPX"], check_freq=False)
    assert prices["EURUSD"].iloc[4] == prices["EURUSD"].iloc[3]  # #N/A remplacé par la veille


def test_long_format(tmp_path, reference):
    long = reference.reset_index().melt(id_vars="date", var_name="ticker", value_name="close")
    long.to_csv(tmp_path / "long.csv", index=False)
    prices, report = read_price_file(tmp_path / "long.csv")
    assert report.layout.startswith("long")
    pd.testing.assert_frame_equal(prices[reference.columns], reference, check_freq=False)


def test_excel_file(tmp_path, reference):
    reference.to_excel(tmp_path / "prix.xlsx")
    prices, report = read_price_file(tmp_path / "prix.xlsx")
    pd.testing.assert_frame_equal(prices, reference, check_freq=False)


def test_ambiguous_dates_are_read_day_first_and_noted(tmp_path):
    (tmp_path / "p.csv").write_text("date,EURUSD\n01/02/2026,1.10\n02/02/2026,1.11\n")
    prices, report = read_price_file(tmp_path / "p.csv")
    assert prices.index[0] == pd.Timestamp("2026-02-01")
    assert any("ambiguës" in n for n in report.notes)


def test_typo_is_corrected_but_real_crash_is_kept(tmp_path):
    rows = ["date,SPX", "2026-01-05,100", "2026-01-06,1000", "2026-01-07,101",  # x10 puis /10
            "2026-01-08,85", "2026-01-09,86"]  # -16 % : un vrai krach reste  # fmt: skip
    (tmp_path / "p.csv").write_text("\n".join(rows))
    prices, report = read_price_file(tmp_path / "p.csv")
    assert report.typos == {"SPX": 1}
    assert list(prices["SPX"]) == [100, 100, 101, 85, 86]


def test_missing_file():
    with pytest.raises(MarketDataError, match="introuvable"):
        read_price_file("absent.csv")


def test_no_date_column(tmp_path):
    (tmp_path / "p.csv").write_text("x,EURUSD\nabc,1.1\ndef,1.2\n")
    with pytest.raises(DataQualityError, match="dates"):
        read_price_file(tmp_path / "p.csv")


def test_unreadable_date_is_reported_with_example(tmp_path):
    (tmp_path / "p.csv").write_text("date,EURUSD\n2026-01-05,1.1\n31/31/2026,1.2\n")
    with pytest.raises(DataQualityError, match="31/31/2026"):
        read_price_file(tmp_path / "p.csv")


def test_negative_prices_are_blocking(tmp_path):
    (tmp_path / "p.csv").write_text("date,OIL\n2026-01-05,10\n2026-01-06,-5\n")
    with pytest.raises(DataQualityError, match="positivit"):
        read_price_file(tmp_path / "p.csv")


def test_same_series_in_two_files_is_refused(reference):
    with pytest.raises(DataQualityError, match="plusieurs fichiers"):
        combine_prices([reference[["SPX"]], reference[["SPX", "EURUSD"]]])


@pytest.mark.parametrize(
    "raw, expected",
    [("EUR/USD", "EURUSD"), ("^GSPC", "SPX"), ("Euro Stoxx 50", "SX5E"), ("Brent clôture", "BRENT_CLOTURE")],
)
def test_canonical_names(raw, expected):
    assert canonical_name(raw) == expected
