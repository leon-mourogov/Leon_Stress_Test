"""engine.py — moteur de stress : revalorisation complète d'un book sous des scénarios."""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from quantlab.errors import ConfigError
from quantlab.pricing.instruments import build

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Position:
    id: str
    instrument: object


def load_book(path):
    """Book JSON -> liste de Position. Toute anomalie du fichier est une ConfigError."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Book introuvable : {path}")
    try:
        specs = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path.name} : JSON invalide ligne {e.lineno} ({e.msg})") from e
    positions = []
    for i, spec in enumerate(specs, start=1):
        spec = dict(spec)
        try:
            trade_id = spec.pop("id")
            positions.append(Position(trade_id, build(spec)))
        except (KeyError, TypeError, ValueError) as e:
            raise ConfigError(f"{path.name}, trade n°{i} : {e}") from e
    if not positions:
        raise ConfigError(f"{path.name} : book vide, aucune position à valoriser")
    ids = [p.id for p in positions]
    if len(ids) != len(set(ids)):
        raise ConfigError(f"{path.name} : identifiants de trade en double")
    return positions


def to_base(amount, ccy, md, base="EUR"):
    """Convertit en devise de référence AVEC le change du marché fourni (choqué ou non)."""
    if ccy == base:
        return amount
    if base == "EUR" and ccy == "USD":
        return amount / md.spot("EURUSD")
    raise ValueError(f"Conversion {ccy} -> {base} non gérée")


def value_book(positions, md, base="EUR"):
    return {p.id: to_base(float(p.instrument.value(md)), p.instrument.ccy, md, base) for p in positions}


def run_stress(positions, md, scenarios, base="EUR"):
    """P&L de chaque position sous chaque scénario, format long."""
    t0 = time.perf_counter()
    base_values = value_book(positions, md, base)
    rows = []
    for sc in scenarios:
        shocked_values = value_book(positions, sc.apply(md), base)
        log.debug(
            "Scénario %s : P&L total %.0f", sc.name, sum(shocked_values.values()) - sum(base_values.values())
        )
        for p in positions:
            rows.append(
                {
                    "scenario": sc.name,
                    "position": p.id,
                    "type": type(p.instrument).__name__,
                    "pnl": shocked_values[p.id] - base_values[p.id],
                }
            )
    log.info(
        "Stress : %d scénarios x %d positions en %.1f s",
        len(scenarios),
        len(positions),
        time.perf_counter() - t0,
    )
    return pd.DataFrame(rows)
