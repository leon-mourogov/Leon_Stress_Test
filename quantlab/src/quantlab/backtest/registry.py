"""registry.py — construire des stratégies depuis une config, lancer des lots, ne rien recalculer."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from quantlab.backtest.engine import run_backtest
from quantlab.backtest.metrics import performance
from quantlab.backtest.strategy import BuyAndHold, Momentum, SMACross, VolTarget

log = logging.getLogger(__name__)

REGISTRY = {"buy_hold": BuyAndHold, "sma": SMACross, "momentum": Momentum}


def build_strategy(spec):
    """{"type": "sma", "params": {...}, "vol_target": {...}?} -> Strategy."""
    if spec["type"] not in REGISTRY:
        raise KeyError(f"Stratégie inconnue {spec['type']!r}. Connues : {sorted(REGISTRY)}")
    strat = REGISTRY[spec["type"]](**spec.get("params", {}))
    if "vol_target" in spec:
        strat = VolTarget(strat, **spec["vol_target"])
    return strat


def data_fingerprint(prices):
    """Empreinte des données : si un seul prix change, l'empreinte change."""
    raw = pd.util.hash_pandas_object(prices, index=True).values.tobytes()
    return hashlib.sha256(raw).hexdigest()[:12]


def run_id(strategy, data_fp, cost_bps):
    """Identifiant d'un essai : stratégie COMPLÈTE (paramètres par défaut inclus), données, coûts."""
    canonical = json.dumps(
        {"strategy": strategy.name, "data": data_fp, "cost_bps": float(cost_bps)}, sort_keys=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def run_batch(prices, specs, cost_bps=5.0, results_dir="results"):
    out = Path(results_dir)
    out.mkdir(exist_ok=True)
    log_path = out / "log.jsonl"
    data_fp = data_fingerprint(prices)
    rows, n_cached = [], 0
    for spec in specs:
        strat = build_strategy(spec)
        rid = run_id(strat, data_fp, cost_bps)
        path = out / f"{rid}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            n_cached += 1
        else:
            bt = run_backtest(prices, strat.signal(prices), cost_bps)
            record = {
                "run_id": rid,
                "name": strat.name,
                "spec": spec,
                "data": data_fp,
                "cost_bps": cost_bps,
                "metrics": performance(bt),
                "created": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            with log_path.open("a", encoding="utf-8") as f:  # journal de TOUS les essais
                f.write(
                    json.dumps({"run_id": rid, "name": strat.name, "sharpe": record["metrics"]["sharpe"]})
                    + "\n"
                )
        rows.append({"run_id": rid, "name": record["name"], **record["metrics"]})
    log.info("%d essais, %d déjà en cache, %d calculés", len(specs), n_cached, len(specs) - n_cached)
    return pd.DataFrame(rows).set_index("run_id")
