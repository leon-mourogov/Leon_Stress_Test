"""log.py — configuration du logging, appelée UNE fois par le point d'entrée (CLI, pipeline)."""

import logging
import logging.handlers
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"


def setup_logging(level="INFO", logfile=None):
    """Console au niveau `level` ; fichier (optionnel) au niveau DEBUG, avec rotation."""
    root = logging.getLogger("quantlab")
    root.setLevel(logging.DEBUG)
    for h in root.handlers[:]:  # rappel de la fonction : pas de doublons
        # libère le fichier journal : sous Windows, un fichier ouvert ne peut être ni déplacé ni effacé
        h.close()
        root.removeHandler(h)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(FORMAT, datefmt="%H:%M:%S"))
    root.addHandler(console)

    if logfile:
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
        file = logging.handlers.RotatingFileHandler(
            logfile, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        file.setLevel(logging.DEBUG)
        file.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(file)
    return root
