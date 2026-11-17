"""Tests de l'API : mêmes chiffres que l'app, erreurs propres."""

import pytest
from fastapi.testclient import TestClient

from quantlab.api import app
from quantlab.services import make_market, price

client = TestClient(app)
CALL = {"K": 5000, "T": 1.0, "call": True, "notional": 200}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_price_matches_services():
    r = client.post("/price", json={"product": CALL, "market": {"vol": 0.18}})
    assert r.status_code == 200
    expected = price({"type": "european", "underlying": "SX5E", **CALL}, make_market(vol=0.18))
    assert r.json()["valeur"] == pytest.approx(expected["valeur"])


def test_negative_strike_rejected():
    r = client.post("/price", json={"product": {**CALL, "K": -1}})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "product", "K"]


def test_unknown_underlying_is_422_not_500():
    r = client.post("/price", json={"product": {**CALL, "underlying": "CAC40"}})
    assert r.status_code == 422
    assert "CAC40" in r.json()["detail"]
