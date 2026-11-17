"""storage.py — base SQLite via SQLAlchemy Core : prix, métriques de risque, journal des exécutions."""

import logging
from datetime import date

import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.sqlite import insert

log = logging.getLogger(__name__)
metadata = MetaData()

prices = Table(
    "prices",
    metadata,
    Column("date", Date, primary_key=True),
    Column("series", String, primary_key=True),  # 'EURUSD', 'SPX'...
    Column("value", Float, nullable=False),
    Column("source", String, nullable=False),
)

metrics = Table(
    "metrics",
    metadata,
    Column("as_of", Date, primary_key=True),
    Column("name", String, primary_key=True),  # 'var99', 'es975', 'stress_worst'...
    Column("value", Float, nullable=False),
)

runs = Table(
    "runs",
    metadata,
    Column("run_id", Integer, primary_key=True, autoincrement=True),
    Column("as_of", Date, nullable=False),
    Column("started_at", DateTime, nullable=False),
    Column("status", String, nullable=False),  # OK / PARTIAL / FAILED
    Column("duration_s", Float),
    Column("n_warnings", Integer, default=0),
    Column("message", String),
)


def get_engine(url="sqlite:///quantlab.db"):
    engine = create_engine(url)
    metadata.create_all(engine)  # crée les tables absentes, ne touche pas aux autres
    return engine


def upsert_prices(engine, df, source):
    """df : index date, une colonne par série. Insère ou met à jour (idempotent)."""
    long = df.stack().rename("value").reset_index()
    long.columns = ["date", "series", "value"]
    rows = [
        {"date": r.date.date(), "series": r.series, "value": float(r.value), "source": source}
        for r in long.itertuples(index=False)
    ]
    stmt = insert(prices)
    stmt = stmt.on_conflict_do_update(
        index_elements=["date", "series"],
        set_={"value": stmt.excluded.value, "source": stmt.excluded.source},
    )
    with engine.begin() as conn:  # transaction : tout ou rien
        conn.execute(stmt, rows)  # liste de dicts -> executemany
    log.info("upsert_prices : %d lignes (%s)", len(rows), source)
    return len(rows)


def read_prices(engine, series, start=None, end=None):
    q = select(prices.c.date, prices.c.series, prices.c.value).where(prices.c.series.in_(series))
    if start:
        q = q.where(prices.c.date >= start)
    if end:
        q = q.where(prices.c.date <= end)
    with engine.connect() as conn:
        df = pd.DataFrame(conn.execute(q).all(), columns=["date", "series", "value"])
    wide = df.pivot(index="date", columns="series", values="value")
    # pandas 3 : des objets date donnent datetime64[s], un CSV donne datetime64[us] -> on harmonise
    wide.index = pd.to_datetime(wide.index).as_unit("us")
    return wide[list(series)]


def save_metrics(engine, as_of: date, values: dict):
    rows = [{"as_of": as_of, "name": k, "value": float(v)} for k, v in values.items()]
    stmt = insert(metrics)
    stmt = stmt.on_conflict_do_update(index_elements=["as_of", "name"], set_={"value": stmt.excluded.value})
    with engine.begin() as conn:
        conn.execute(stmt, rows)


def count_rows(engine, table):
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def log_run(engine, as_of, started_at, status, duration_s, n_warnings, message=""):
    with engine.begin() as conn:
        conn.execute(
            runs.insert().values(
                as_of=as_of,
                started_at=started_at,
                status=status,
                duration_s=duration_s,
                n_warnings=n_warnings,
                message=message[:500],
            )
        )


def last_runs(engine, n=10):
    q = select(runs).order_by(runs.c.run_id.desc()).limit(n)
    with engine.connect() as conn:
        return pd.DataFrame(conn.execute(q).all(), columns=[c.name for c in runs.columns])


def metric_history(engine, name, end, days=30):
    """Les `days` dernières valeurs d'une métrique jusqu'à `end` inclus."""
    q = (
        select(metrics.c.as_of, metrics.c.value)
        .where(metrics.c.name == name, metrics.c.as_of <= end)
        .order_by(metrics.c.as_of.desc())
        .limit(days)
    )
    with engine.connect() as conn:
        df = pd.DataFrame(conn.execute(q).all(), columns=["as_of", name])
    return df.sort_values("as_of").set_index("as_of")[name]
