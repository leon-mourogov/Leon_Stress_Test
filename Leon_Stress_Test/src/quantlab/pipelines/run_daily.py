"""run_daily.py — rapport de risque quotidien.

    python -m quantlab.pipelines.run_daily --date 2025-12-31 --config config/settings.yaml
    python -m quantlab.pipelines.run_daily --prices mes_prix.xlsx     # sur un fichier de prix quelconque

Chaque étape reçoit le contexte et l'enrichit. Une étape BLOQUANTE qui échoue arrête tout
(code 2) ; une étape NON BLOQUANTE qui échoue est notée et le rapport sort « INCOMPLET » (code 1).
"""

import copy
import json
import logging
import pickle
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from quantlab.alerts import send_alert
from quantlab.config import load_settings
from quantlab.errors import DataQualityError, MarketDataError, QuantLabError
from quantlab.log import setup_logging
from quantlab.market.curve import YieldCurve
from quantlab.market.data import MarketData
from quantlab.market.importer import load_price_files
from quantlab.pipelines.cli import EXIT_FAILED, EXIT_OK, EXIT_PARTIAL, parse_args, previous_business_day
from quantlab.risk.engine import Position, load_book, run_stress, to_base
from quantlab.risk.library import load_scenarios
from quantlab.risk.scenario import BASE
from quantlab.risk.var import historical_scenarios, pnl_distribution, var_es
from quantlab.storage import get_engine, log_run, read_prices, save_metrics, upsert_prices

# pas __name__ : lancé avec "python -m", ce module s'appelle "__main__" et sortirait de l'arbre "quantlab"
log = logging.getLogger("quantlab.pipelines.run_daily")
MAX_STALE_DAYS = 5


@dataclass
class Context:
    as_of: date
    settings: object
    out_dir: Path
    data: dict = field(default_factory=dict)  # résultats des étapes
    warnings: list = field(default_factory=list)  # étapes non bloquantes en échec
    error: str = ""  # cause de l'échec bloquant, reprise dans l'alerte

    @property
    def status(self):
        return "PARTIAL" if self.warnings else "OK"


# ---------------------------------------------------------------- étapes


def step_inputs(ctx):
    p = ctx.settings.paths
    ctx.data["book"] = load_book(p.book)
    ctx.data["scenarios"] = [BASE] + load_scenarios(p.scenarios)
    ctx.data["limits"] = json.loads(Path(p.limits).read_text(encoding="utf-8"))


def step_market(ctx):
    m = ctx.settings.market
    curve = lambda r: YieldCurve((0.25, 1.0, 5.0, 10.0), (r,) * 4)  # noqa: E731
    md = MarketData(ctx.as_of, m.spots, m.vols, {ccy: curve(r) for ccy, r in m.rates.items()}, m.div_yields)
    missing = {}
    for p in ctx.data["book"]:  # contrôle de complétude : chaque sous-jacent du book a un spot et une vol
        u = p.instrument.underlying
        if u not in md.spots or u not in md.vols:
            missing.setdefault(u, []).append(p.id)
    if missing:
        detail = ", ".join(f"{u} (positions {', '.join(ids)})" for u, ids in missing.items())
        raise MarketDataError(f"Spot ou vol manquant pour {detail}")
    ctx.data["md"] = md


def step_history(ctx):
    """ETL : fichiers de prix -> base (idempotent) -> lecture jusqu'à la date du rapport."""
    engine = ctx.data["engine"]
    prices, reports = load_price_files(ctx.settings.paths.prices)
    for rep in reports:
        for issue in rep.issues:
            log.warning("[history] %s : %s", issue.check, issue.detail)
    upsert_prices(engine, prices, source="import")
    hist = read_prices(engine, list(prices.columns), end=ctx.as_of)
    if hist.empty:
        raise DataQualityError(f"Aucun prix historique avant le {ctx.as_of}")
    ctx.data["history"] = hist


def factor_mapping(factors, columns, proxies):
    """Série historique de chaque facteur : la sienne si elle existe, sinon le proxy configuré."""
    mapping = {}
    for f in factors:
        if f in columns:
            mapping[f] = f
        elif proxies.get(f) in columns:
            mapping[f] = proxies[f]
    return mapping


def step_valuation(ctx):
    md, base = ctx.data["md"], ctx.settings.risk.base_currency
    rows = []
    for p in ctx.data["book"]:
        ins = p.instrument
        g = ins.greeks(md)
        rows.append(
            {
                "position": p.id,
                "produit": type(ins).__name__,
                "devise": ins.ccy,
                "valeur_eur": to_base(float(ins.value(md)), ins.ccy, md, base),
                "delta": g["delta"],
                "gamma": g["gamma"],
                "vega": g["vega"],
            }
        )
    ctx.data["valuation"] = pd.DataFrame(rows).set_index("position")


def step_stress(ctx):
    res = run_stress(ctx.data["book"], ctx.data["md"], ctx.data["scenarios"])
    grid = res.pivot_table(index="scenario", columns="position", values="pnl", aggfunc="sum")
    grid = grid.reindex([s.name for s in ctx.data["scenarios"]])
    if grid.loc["Base"].abs().max() > 1e-6:
        raise QuantLabError("Scénario Base non nul : moteur de stress incohérent")
    grid["TOTAL"] = grid.sum(axis=1)
    ctx.data["stress"] = grid


def step_var(ctx):
    if "history" not in ctx.data:  # l'étape history est non bloquante : elle a pu échouer
        raise DataQualityError("Historique de prix indisponible : VaR non calculée")
    hist, r = ctx.data["history"], ctx.settings.risk
    age = (pd.Timestamp(ctx.as_of) - hist.index[-1]).days
    if age > MAX_STALE_DAYS:
        raise DataQualityError(f"Historique de prix arrêté au {hist.index[-1]:%Y-%m-%d} ({age} jours)")
    fast = []
    for p in ctx.data["book"]:
        ins = p.instrument
        if hasattr(
            ins, "n_paths"
        ):  # tout produit Monte Carlo : moins de chemins pour les 500 revalorisations
            ins = copy.copy(ins)
            ins.n_paths = r.mc_paths_var
        fast.append(Position(p.id, ins))
    mapping = factor_mapping(ctx.data["md"].spots, hist.columns, r.factor_series)
    unmapped = sorted({p.instrument.underlying for p in ctx.data["book"]} - set(mapping))
    if unmapped:
        raise DataQualityError(
            f"Pas d'historique pour {unmapped} : ajoutez la série aux fichiers de prix "
            "ou un proxy dans risk.factor_series"
        )
    scen = historical_scenarios(hist, mapping, window=r.var_window_days)
    pnl = pnl_distribution(fast, ctx.data["md"], scen, r.base_currency)
    var, _ = var_es(pnl, r.var_level)
    _, es = var_es(pnl, r.es_level)
    ctx.data["var"] = {"var99": var, "es975": es}
    ctx.data["var_pnl"] = pnl


def step_limits(ctx):
    metrics = {"stress_worst": float(-ctx.data["stress"]["TOTAL"].min()), **ctx.data.get("var", {})}
    rows = [
        {"metrique": k, "valeur": metrics[k], "limite": lim, "utilisation": metrics[k] / lim}
        for k, lim in ctx.data["limits"].items()
        if k in metrics
    ]
    ctx.data["metrics"] = metrics
    ctx.data["limits_usage"] = pd.DataFrame(rows).set_index("metrique")


def step_report(ctx):
    from quantlab.reporting import write_reports  # import local : matplotlib/openpyxl seulement ici

    ctx.data["files"] = write_reports(ctx)


def step_archive(ctx):
    save_metrics(ctx.data["engine"], ctx.as_of, ctx.data["metrics"])


# (nom, fonction, bloquante ?)
STEPS = [
    ("inputs", step_inputs, True),
    ("market", step_market, True),
    ("history", step_history, False),
    ("valuation", step_valuation, True),
    ("stress", step_stress, True),
    ("var", step_var, False),
    ("limits", step_limits, True),
    ("archive", step_archive, True),  # AVANT le rapport : le graphique d'historique lit la base
    ("report", step_report, True),
]
CHECKPOINTED = {"valuation", "stress", "var"}  # étapes coûteuses : résultat sauvegardé


# ---------------------------------------------------------------- orchestration


def _checkpoint(ctx, name):
    return ctx.out_dir / "state" / f"{name}.pkl"


def run_daily(as_of, settings, force=False, engine=None):
    t0, started = time.perf_counter(), datetime.now()
    out_dir = Path(settings.paths.reports) / as_of.isoformat()
    ctx = Context(as_of, settings, out_dir)
    ctx.data["engine"] = engine or get_engine(settings.database.url)
    done_flag = out_dir / "DONE"
    if done_flag.exists() and done_flag.read_text(encoding="utf-8") == "OK" and not force:
        log.info("Rapport du %s déjà produit (%s) : rien à faire. --force pour le refaire.", as_of, out_dir)
        return EXIT_OK, ctx
    status, message = "FAILED", ""
    try:
        for name, func, blocking in STEPS:
            ckpt = _checkpoint(ctx, name)
            if name in CHECKPOINTED and ckpt.exists() and not force:
                ctx.data.update(pickle.loads(ckpt.read_bytes()))
                log.info("[%s] repris depuis le point de sauvegarde", name)
                continue
            t = time.perf_counter()
            before = set(ctx.data)
            try:
                func(ctx)
            except QuantLabError as e:
                if blocking:
                    raise
                ctx.warnings.append(f"{name} : {e}")
                log.warning("[%s] étape non bloquante en échec : %s", name, e)
                continue
            if name in CHECKPOINTED:
                ckpt.parent.mkdir(parents=True, exist_ok=True)
                ckpt.write_bytes(pickle.dumps({k: ctx.data[k] for k in set(ctx.data) - before}))
            log.info("[%s] OK en %.1f s", name, time.perf_counter() - t)
        status = ctx.status
        message = " | ".join(ctx.warnings)
        done_flag.write_text(status, encoding="utf-8")
        code = EXIT_PARTIAL if ctx.warnings else EXIT_OK
    except QuantLabError as e:
        message = ctx.error = f"{type(e).__name__}: {e}"
        log.error("Échec bloquant : %s", message)
        code = EXIT_FAILED
    except Exception as e:  # bug de programmation : on journalise la trace complète
        message = ctx.error = f"{type(e).__name__}: {e}"
        log.exception("Erreur inattendue")
        code = EXIT_FAILED
    duration = time.perf_counter() - t0
    log_run(ctx.data["engine"], as_of, started, status, duration, len(ctx.warnings), message)
    log.info("Fin : %s en %.1f s (code %d)", status, duration, code)
    return code, ctx


def main(argv=None):
    args = parse_args(argv)
    try:
        settings = load_settings(args.config)
        if args.prices:  # fichiers fournis en ligne de commande : ils remplacent ceux de la configuration
            settings.paths.prices = [Path(p).resolve() for p in args.prices]
            if args.date is None:  # date du rapport = dernière date commune des fichiers
                prices, _ = load_price_files(settings.paths.prices)
                args.date = prices.index[-1].date()
    except QuantLabError as e:
        print(f"Configuration : {e}", file=sys.stderr)
        return EXIT_FAILED
    if args.date is None:
        args.date = previous_business_day()
    setup_logging(args.log_level, logfile=Path(settings.paths.logs) / "run_daily.log")
    code, ctx = run_daily(args.date, settings, force=args.force)
    if code != EXIT_OK:
        label = "INCOMPLET" if code == EXIT_PARTIAL else "ÉCHEC"
        body = "\n".join(
            [
                f"Rapport du {args.date} : {label} (code {code}).",
                *([f"Cause : {ctx.error}"] if ctx.error else []),
                *ctx.warnings,
                "",
                f"Journal : {Path(settings.paths.logs) / 'run_daily.log'}",
            ]
        )
        send_alert(settings.alerts, f"[quantlab] Rapport de risque {args.date} : {label}", body)
    return code


if __name__ == "__main__":
    sys.exit(main())
