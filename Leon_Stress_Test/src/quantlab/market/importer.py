"""importer.py — lecture de fichiers de prix quelconques (CSV ou Excel) vers un format unique.

Le format interne est un DataFrame « large » : index = dates triées sans doublon, une colonne
par série (EURUSD, SPX...), des nombres. Tout fichier passe par ici, qu'il vienne d'un export
Excel, d'un terminal de marché ou d'une API :

- séparateur (``,`` ``;`` tabulation ``|``), encodage (UTF-8 ou Windows) et virgule décimale détectés ;
- colonne de date reconnue par son nom ou par son contenu ; formats ISO, jour/mois, mois/jour ;
- format « large » (une colonne par série) ou « long » (date, série, valeur) ;
- noms de séries usuels ramenés à un nom canonique (``EUR/USD`` -> ``EURUSD``, ``^GSPC`` -> ``SPX``) ;
- nettoyage : doublons, valeurs manquantes, erreurs de saisie isolées ; contrôles qualité.

Chaque décision est consignée dans un :class:`ImportReport` : rien n'est corrigé en silence.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from quantlab.errors import DataQualityError, MarketDataError
from quantlab.market.quality import DataQualityChecker, Issue

log = logging.getLogger(__name__)

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
DATE_COLUMNS = {"date", "dates", "jour", "day", "time", "time_period", "datetime", "timestamp", "as_of"}
SERIES_COLUMNS = {"series", "serie", "série", "ticker", "symbol", "instrument", "underlying", "sous-jacent"}
VALUE_COLUMNS = {
    "close", "adj close", "adj_close", "price", "prix", "value", "valeur", "last", "px_last",
    "cours", "obs_value", "cloture", "clôture", "fixing",
}  # fmt: skip
MISSING_TOKENS = {"", "-", "–", "—", "na", "n/a", "#n/a", "#n/a n/a", "nan", "null", "none", "#value!"}
ALIASES = {
    "EURUSD": {"eur/usd", "eurusd=x", "eur usd", "eurusd curncy", "eur-usd"},
    "USDJPY": {"usd/jpy", "usdjpy=x", "usd jpy", "usdjpy curncy", "usd-jpy"},
    "SPX": {"s&p 500", "s&p500", "sp500", "^gspc", "spx index", "s&p 500 index"},
    "SX5E": {"euro stoxx 50", "eurostoxx50", "euro stoxx50", "^stoxx50e", "sx5e index", "stoxx50e"},
}
DATE_FORMATS = {
    "%Y-%m-%d": "AAAA-MM-JJ",
    "%Y-%m-%d %H:%M:%S": "AAAA-MM-JJ hh:mm:ss",
    "%Y/%m/%d": "AAAA/MM/JJ",
    "%Y%m%d": "AAAAMMJJ",
    "%d/%m/%Y": "JJ/MM/AAAA",
    "%m/%d/%Y": "MM/JJ/AAAA",
    "%d.%m.%Y": "JJ.MM.AAAA",
    "%d-%m-%Y": "JJ-MM-AAAA",
    "%d/%m/%y": "JJ/MM/AA",
    "%m/%d/%y": "MM/JJ/AA",
}


@dataclass
class ImportReport:
    """Ce que l'importateur a compris du fichier et ce qu'il a corrigé."""

    source: str
    layout: str = "large"
    separator: str | None = None
    decimal: str = "."
    encoding: str | None = None
    date_column: str = ""
    date_format: str = ""
    rows: int = 0
    first_date: str = ""
    last_date: str = ""
    series: list[str] = field(default_factory=list)
    renamed: dict[str, str] = field(default_factory=dict)
    dropped_columns: list[str] = field(default_factory=list)
    duplicates: int = 0
    missing: dict[str, int] = field(default_factory=dict)
    typos: dict[str, int] = field(default_factory=dict)
    non_numeric: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    def summary(self) -> str:
        """Résumé lisible, une information par ligne."""
        sep = {",": "virgule", ";": "point-virgule", "\t": "tabulation", "|": "barre"}.get(
            self.separator, "-"
        )
        lines = [
            f"Fichier          : {self.source}",
            f"Format           : {self.layout}, séparateur {sep}, décimale '{self.decimal}'"
            + (f", encodage {self.encoding}" if self.encoding else ""),
            f"Dates            : colonne '{self.date_column}', format {self.date_format},"
            f" {self.rows} lignes du {self.first_date} au {self.last_date}",
            f"Séries           : {', '.join(self.series)}",
        ]
        if self.renamed:
            lines.append("Noms reconnus    : " + ", ".join(f"{a} -> {b}" for a, b in self.renamed.items()))
        if self.dropped_columns:
            lines.append(f"Colonnes ignorées: {', '.join(self.dropped_columns)} (non numériques)")
        lines.append(
            f"Nettoyage        : {self.duplicates} doublon(s) de date, "
            f"{sum(self.missing.values())} valeur(s) manquante(s), "
            f"{sum(self.typos.values())} erreur(s) de saisie corrigée(s), "
            f"{sum(self.non_numeric.values())} valeur(s) non numérique(s)"
        )
        lines += [f"Remarque         : {n}" for n in self.notes]
        lines += [f"Contrôle [{i.severity}] : {i.check} - {i.detail}" for i in self.issues]
        return "\n".join(lines)


# ---------------------------------------------------------------- lecture brute


def _decode(raw: bytes, report: ImportReport) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            report.encoding = "UTF-8" if encoding == "utf-8-sig" else "Windows-1252"
            return text
        except UnicodeDecodeError:
            continue
    raise DataQualityError(f"{report.source} : encodage du fichier non reconnu")


def _sniff_separator(text: str) -> str:
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {s: sample.count(s) for s in (";", ",", "\t", "|")}
        return max(counts, key=counts.get)


def _read_raw(source, name: str, report: ImportReport) -> pd.DataFrame:
    """Lit le fichier en texte brut (tout en chaînes) : l'interprétation vient ensuite."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise MarketDataError(f"Fichier de prix introuvable : {path}")
        raw = path.read_bytes()
    else:  # bytes, ou objet fichier (téléversement dans l'application)
        raw = source if isinstance(source, bytes) else source.read()
    if Path(name).suffix.lower() in EXCEL_SUFFIXES:
        report.layout, report.separator = "large (Excel)", None
        try:
            df = pd.read_excel(io.BytesIO(raw), dtype=str)
        except Exception as e:  # fichier corrompu ou pas vraiment un classeur
            raise DataQualityError(f"{name} : classeur Excel illisible ({e})") from e
    else:
        text = _decode(raw, report)
        report.separator = _sniff_separator(text)
        try:
            df = pd.read_csv(
                io.StringIO(text),
                sep=report.separator,
                dtype=str,
                keep_default_na=False,
                skipinitialspace=True,
            )
        except pd.errors.ParserError as e:
            raise DataQualityError(f"{name} : CSV illisible ({e})") from e
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or len(df.columns) < 2:
        raise DataQualityError(f"{name} : il faut au moins une colonne de dates et une colonne de prix")
    return df


# ---------------------------------------------------------------- dates


def _parse_dates(values: pd.Series, report: ImportReport) -> pd.DatetimeIndex:
    text = values.astype(str).str.strip()
    filled = text[text != ""]
    candidates = []
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(filled, format=fmt, errors="coerce")
        if parsed.notna().all():
            candidates.append(fmt)
    if not candidates:
        parsed = pd.to_datetime(filled, errors="coerce", dayfirst=True)
        bad = filled[parsed.isna()]
        if len(bad):
            raise DataQualityError(
                f"{report.source} : dates illisibles, par exemple {list(bad.head(3))} "
                "(formats acceptés : AAAA-MM-JJ, JJ/MM/AAAA, MM/JJ/AAAA...)"
            )
        report.date_format = "reconnu automatiquement"
    else:
        fmt = candidates[0]
        if "%d/%m/%Y" in candidates and "%m/%d/%Y" in candidates:
            report.notes.append("dates ambiguës (jour et mois tous deux ≤ 12) : lues en jour/mois")
        report.date_format = DATE_FORMATS[fmt]
        parsed = pd.to_datetime(filled, format=fmt)
    dates = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    dates[filled.index] = parsed
    return pd.DatetimeIndex(dates)


def _find_date_column(df: pd.DataFrame) -> str:
    for c in df.columns:
        if c.lower() in DATE_COLUMNS:
            return c
    for c in df.columns:  # sinon : la première colonne dont le contenu ressemble à des dates
        sample = df[c].astype(str).str.strip().head(20)
        if pd.to_datetime(sample, errors="coerce", format="mixed", dayfirst=True).notna().mean() > 0.9:
            return c
    raise DataQualityError("aucune colonne de dates reconnue (nommez-la 'date')")


# ---------------------------------------------------------------- nombres


def _to_number(col: pd.Series, decimal_comma: bool) -> pd.Series:
    s = col.astype(str).str.strip().str.replace(r"[\s  ']", "", regex=True)
    s = s.where(~s.str.lower().isin(MISSING_TOKENS))
    if decimal_comma:
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        s = s.str.replace(",", "", regex=False)  # séparateur de milliers anglo-saxon
    return pd.to_numeric(s, errors="coerce")


def _uses_decimal_comma(df: pd.DataFrame, separator: str | None) -> bool:
    if separator == ";":  # export Excel français
        return True
    text = df.astype(str).stack()
    comma = text.str.fullmatch(r"-?\d+,\d+").sum()
    dot = text.str.fullmatch(r"-?\d+\.\d+").sum()
    return bool(comma > dot)


# ---------------------------------------------------------------- noms


def canonical_name(name: str) -> str:
    """Nom de série canonique : 'EUR/USD' -> 'EURUSD', '^GSPC' -> 'SPX', 'brent' -> 'BRENT'."""
    key = re.sub(r"\s+", " ", name.strip().lower())
    for canon, aliases in ALIASES.items():
        if key == canon.lower() or key in aliases:
            return canon
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_]", "", plain.strip().upper().replace(" ", "_")) or name


# ---------------------------------------------------------------- import complet


def read_price_file(source, name: str | None = None, jump: float = 0.20) -> tuple[pd.DataFrame, ImportReport]:
    """Lit un fichier de prix (chemin, octets ou fichier ouvert) et renvoie (prix, rapport).

    ``jump`` : une variation de plus de ``jump`` (20 %) suivie le lendemain d'une variation de sens
    inverse de plus de ``jump`` est traitée comme une erreur de saisie (un x10 puis un /10) et remplacée
    par la veille. Le seuil est assez haut pour ne jamais effacer un vrai krach.
    """
    name = name or (Path(source).name if isinstance(source, (str, Path)) else "fichier")
    report = ImportReport(source=name)
    df = _read_raw(source, name, report)

    date_col = _find_date_column(df)
    report.date_column = date_col
    values = df.drop(columns=date_col).astype(str).apply(lambda c: c.str.strip().str.lower())
    empty = values.isin(MISSING_TOKENS).all(axis=1) | (df[date_col].astype(str).str.strip() == "")
    if empty.any():  # lignes vides, titres ou pied de page (« Source : ... ») : aucune valeur à lire
        report.notes.append(f"{int(empty.sum())} ligne(s) sans aucune valeur ignorée(s)")
    df = df[~empty]
    dates = _parse_dates(df[date_col], report)

    lower = {c.lower(): c for c in df.columns}
    series_col = next((lower[c] for c in lower if c in SERIES_COLUMNS), None)
    others = [c for c in df.columns if c not in (date_col, series_col)]
    decimal_comma = _uses_decimal_comma(df[others], report.separator)
    report.decimal = "," if decimal_comma else "."

    if series_col is not None:  # format long : date, série, valeur
        value_cols = [c for c in others if c.lower() in VALUE_COLUMNS] or others[:1]
        report.layout = "long (date, série, valeur)"
        long = pd.DataFrame(
            {
                "date": dates,
                "series": df[series_col].astype(str).str.strip().to_numpy(),
                "value": _to_number(df[value_cols[0]], decimal_comma).to_numpy(),
            }
        )
        report.duplicates = int(long.duplicated(["date", "series"]).sum())
        wide = long.drop_duplicates(["date", "series"]).pivot(index="date", columns="series", values="value")
        wide.columns.name = None
    else:
        wide = pd.DataFrame(index=dates)
        for c in others:
            numbers = _to_number(df[c], decimal_comma)
            raw = df[c].astype(str).str.strip().str.lower()
            not_number = numbers.isna() & ~raw.isin(MISSING_TOKENS)
            if not_number.sum() >= numbers.notna().sum():  # colonne de texte (commentaire, devise...)
                report.dropped_columns.append(c)
                continue
            if not_number.any():
                report.non_numeric[c] = int(not_number.sum())
            wide[c] = numbers.to_numpy()
        if wide.empty or not len(wide.columns):
            raise DataQualityError(f"{name} : aucune colonne de prix numérique")
        report.duplicates = int(wide.index.duplicated().sum())
        wide = wide[~wide.index.duplicated(keep="first")]

    # noms : une seule colonne générique ('close', 'price') prend le nom du fichier (spx.csv -> SPX)
    rename = {}
    for c in wide.columns:
        if len(wide.columns) == 1 and c.lower() in VALUE_COLUMNS:
            rename[c] = canonical_name(Path(name).stem)
        else:
            rename[c] = canonical_name(c)
    report.renamed = {a: b for a, b in rename.items() if a != b}
    wide = wide.rename(columns=rename).sort_index()
    wide.index.name = "date"
    if wide.columns.duplicated().any():
        raise DataQualityError(f"{name} : plusieurs colonnes désignent la même série {list(wide.columns)}")

    # nettoyage : erreurs de saisie isolées, trous d'un jour
    report.missing = {c: int(n) for c, n in wide.isna().sum().items() if n}
    ret = wide.pct_change(fill_method=None)
    typo = (ret.abs() > jump) & (ret.shift(-1).abs() > jump) & (ret * ret.shift(-1) < 0)
    report.typos = {c: int(n) for c, n in typo.sum().items() if n}
    wide = wide.mask(typo).ffill(limit=1)

    checker = DataQualityChecker()
    for c in wide.columns:
        report.issues += [Issue(i.severity, f"{c} / {i.check}", i.detail) for i in checker.check(wide[c])]
    blocking = [i for i in report.issues if i.severity == "BLOQUANT"]
    if blocking:
        raise DataQualityError(f"{name} : " + " ; ".join(f"{i.check} : {i.detail}" for i in blocking))

    report.series, report.rows = list(wide.columns), len(wide)
    report.first_date, report.last_date = f"{wide.index[0]:%Y-%m-%d}", f"{wide.index[-1]:%Y-%m-%d}"
    log.info(
        "%s : %d ligne(s), séries %s, %d doublon(s), %d manquante(s), %d erreur(s) de saisie",
        name, report.rows, report.series, report.duplicates,
        sum(report.missing.values()), sum(report.typos.values()),
    )  # fmt: skip
    return wide, report


def combine_prices(frames) -> pd.DataFrame:
    """Réunit plusieurs tableaux de prix en gardant les dates communes à tous (jointure interne)."""
    prices = frames[0]
    for df in frames[1:]:
        clash = set(prices.columns) & set(df.columns)
        if clash:
            raise DataQualityError(f"séries présentes dans plusieurs fichiers : {sorted(clash)}")
        prices = prices.join(df, how="inner")
    if prices.empty:
        raise DataQualityError("aucune date commune entre les fichiers de prix")
    return prices


def load_price_files(paths) -> tuple[pd.DataFrame, list[ImportReport]]:
    """Importe un ou plusieurs fichiers et renvoie (prix aux dates communes, rapports d'import)."""
    results = [read_price_file(p) for p in paths]
    return combine_prices([df for df, _ in results]), [rep for _, rep in results]


def main(argv=None) -> int:
    """python -m quantlab.market.importer FICHIER ... [--save prix.csv] : ce qui a été compris."""
    import argparse
    import sys

    from quantlab.errors import QuantLabError

    p = argparse.ArgumentParser(
        prog="python -m quantlab.market.importer",
        description="Lire, interpréter et contrôler des fichiers de prix (CSV ou Excel .xlsx).",
    )
    p.add_argument("files", nargs="+", metavar="FICHIER")
    p.add_argument("--save", metavar="CSV", help="enregistrer les données nettoyées")
    args = p.parse_args(argv)
    try:
        results = [read_price_file(f) for f in args.files]
        for _, report in results:
            print(report.summary(), end="\n\n")
        prices = combine_prices([df for df, _ in results])
    except QuantLabError as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 2
    print(f"Données prêtes : {len(prices)} dates communes, séries {', '.join(prices.columns)}.")
    if args.save:
        prices.to_csv(args.save)
        print(f"Données nettoyées enregistrées dans {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
