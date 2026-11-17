"""Base SQLite : idempotence, corrections, transactions."""

import math

import pandas as pd
import pytest
from sqlalchemy.exc import IntegrityError

from quantlab.storage import count_rows, get_engine, prices, read_prices, upsert_prices


@pytest.fixture
def engine(tmp_path):
    return get_engine(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def px():
    idx = pd.bdate_range("2026-10-12", periods=5)
    return pd.DataFrame(
        {"EURUSD": [1.16, 1.17, 1.165, 1.17, 1.172], "SPX": [5800.0, 5810, 5795, 5820, 5830]}, idx
    )


def test_load_twice_is_idempotent(engine, px):
    upsert_prices(engine, px, "test")
    upsert_prices(engine, px, "test")
    assert count_rows(engine, prices) == 10


def test_correction_overwrites_value(engine, px):
    upsert_prices(engine, px, "test")
    upsert_prices(engine, px.iloc[[-1]][["SPX"]] * 1.01, "correction")
    assert read_prices(engine, ["SPX"])["SPX"].iloc[-1] == pytest.approx(5830 * 1.01)


def test_round_trip(engine, px):
    upsert_prices(engine, px, "test")
    pd.testing.assert_frame_equal(
        read_prices(engine, ["EURUSD", "SPX"]), px, check_names=False, check_freq=False
    )


def test_failed_batch_writes_nothing(engine, px):
    bad = px.copy()
    bad.iloc[-1, 0] = math.nan  # une valeur manquante -> contrainte NOT NULL
    with pytest.raises(IntegrityError):
        upsert_prices(engine, bad, "bad")
    assert count_rows(engine, prices) == 0  # la transaction a tout annulé
