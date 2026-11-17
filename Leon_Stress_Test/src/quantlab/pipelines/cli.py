"""cli.py — arguments de la ligne de commande du rapport quotidien."""

import argparse
from datetime import date, timedelta

EXIT_OK, EXIT_PARTIAL, EXIT_FAILED = 0, 1, 2


def previous_business_day(today=None):
    d = (today or date.today()) - timedelta(days=1)
    while d.weekday() >= 5:  # 5 = samedi, 6 = dimanche
        d -= timedelta(days=1)
    return d


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"date invalide {text!r} (format attendu : AAAA-MM-JJ)") from None


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m quantlab.pipelines.run_daily",
        description="Rapport de risque quotidien : stress, VaR, limites, Excel et PDF.",
        epilog="Codes de sortie : 0 = OK, 1 = rapport partiel, 2 = échec.",
    )
    p.add_argument(
        "--date",
        type=parse_date,
        default=None,
        help="date de marché (défaut : jour ouvré précédent, ou dernière date des fichiers de --prices)",
    )
    p.add_argument(
        "--prices",
        nargs="+",
        metavar="FICHIER",
        help="fichier(s) de prix CSV ou Excel à utiliser à la place de ceux de la configuration",
    )
    p.add_argument("--config", default="config/settings.yaml", help="fichier de configuration YAML")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--force", action="store_true", help="refaire le rapport même s'il existe déjà")
    return p


def parse_args(argv=None):
    """Arguments analysés ; ``date`` reste None si absente (la date par défaut dépend de --prices)."""
    return build_parser().parse_args(argv)
