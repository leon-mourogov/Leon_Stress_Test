"""watchdog.py — heartbeat : à 8 h 30, le rapport du jour ouvré précédent est-il OK ? Sinon, alerte."""

import sys

from quantlab.alerts import send_alert
from quantlab.config import load_settings
from quantlab.errors import QuantLabError
from quantlab.pipelines.cli import previous_business_day
from quantlab.storage import get_engine, last_runs


def check(settings, today=None):
    """Message d'alerte, ou None si le rapport attendu existe et est OK."""
    expected = previous_business_day(today)
    try:
        runs = last_runs(get_engine(settings.database.url), n=20)
    except Exception as e:  # base absente ou illisible : c'est précisément ce qu'on surveille
        return f"Base des exécutions illisible ({type(e).__name__}: {e})"
    if runs.empty:
        return f"Aucune exécution en base : le pipeline n'a jamais tourné (attendu : {expected})"
    day = runs[runs["as_of"] == expected]
    if day.empty:
        return f"Aucune exécution pour le {expected} : le pipeline n'a pas démarré"
    if "OK" not in set(day["status"]):
        last = day.iloc[0]
        return f"Rapport du {expected} en statut {last['status']} : {last['message']}"
    return None


def main(config="config/settings.yaml", today=None):
    try:
        settings = load_settings(config)
    except QuantLabError as e:
        print(f"ALERTE : configuration illisible : {e}", file=sys.stderr)
        return 2
    problem = check(settings, today)
    if problem is None:
        return 0
    print(f"ALERTE : {problem}", file=sys.stderr)
    send_alert(settings.alerts, "[quantlab] HEARTBEAT : rapport du matin absent", problem)
    return 2


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
