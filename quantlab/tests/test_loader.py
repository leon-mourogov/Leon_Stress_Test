"""Tests du loader BCE sans jamais appeler internet : on remplace la session HTTP."""

from unittest.mock import Mock

import pytest
import requests

from quantlab.errors import MarketDataError, QuantLabError
from quantlab.market.loader import MarketDataLoader

CSV_OK = "KEY,TIME_PERIOD,OBS_VALUE\nX,2026-10-15,1.1650\nX,2026-10-16,1.1702\n"


def response(status, text=""):
    """Fausse réponse HTTP : seuls les attributs utilisés par le loader."""
    r = Mock(status_code=status, text=text)
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(f"{status}", response=r)
    return r


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Les retries attendent 1 s, 2 s, 4 s... : on supprime l'attente pendant les tests."""
    monkeypatch.setattr("quantlab.market.loader.time.sleep", lambda s: None)


def make_loader(tmp_path, *responses):
    session = Mock()
    session.get.side_effect = list(responses)  # chaque appel renvoie l'élément suivant
    return MarketDataLoader(cache_dir=tmp_path, session=session, retries=3), session


def test_parses_ecb_csv(tmp_path):
    loader, session = make_loader(tmp_path, response(200, CSV_OK))
    s = loader.ecb_series("EXR", "D.USD.EUR.SP00.A")
    assert list(s) == [1.1650, 1.1702]
    assert session.get.call_count == 1


def test_retries_after_server_error(tmp_path):
    loader, session = make_loader(tmp_path, response(503), response(200, CSV_OK))
    s = loader.ecb_series("EXR", "D.USD.EUR.SP00.A")
    assert len(s) == 2 and session.get.call_count == 2


def test_client_error_is_not_retried(tmp_path):
    loader, session = make_loader(tmp_path, response(404))
    with pytest.raises(MarketDataError, match="404"):
        loader.ecb_series("EXR", "MAUVAISE.CLE")
    assert session.get.call_count == 1  # un 404 ne se corrigera pas en réessayant


def test_gives_up_after_retries(tmp_path):
    loader, session = make_loader(tmp_path, *[requests.Timeout("lent")] * 3)
    with pytest.raises(QuantLabError):  # attrapable par la classe de base
        loader.ecb_series("EXR", "D.USD.EUR.SP00.A")
    assert session.get.call_count == 3


def test_falls_back_to_cache_when_api_is_down(tmp_path):
    loader, _ = make_loader(tmp_path, response(200, CSV_OK), *[requests.ConnectionError()] * 3)
    loader.ecb_series("EXR", "K")  # 1er appel : remplit le cache
    s = loader.ecb_series("EXR", "K", use_cache_today=False)  # 2e appel : API en panne
    assert list(s) == [1.1650, 1.1702]


def test_empty_series_is_an_error(tmp_path):
    loader, _ = make_loader(tmp_path, response(200, "KEY,TIME_PERIOD,OBS_VALUE\n"))
    with pytest.raises(MarketDataError, match="Aucune observation"):
        loader.ecb_series("EXR", "K")


def test_every_request_has_a_timeout(tmp_path):
    loader, session = make_loader(tmp_path, response(200, CSV_OK))
    loader.ecb_series("EXR", "K")
    _, kwargs = session.get.call_args  # arguments du dernier appel
    assert kwargs["timeout"] == pytest.approx(10.0)
