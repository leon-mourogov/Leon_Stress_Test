"""loader.py — récupération des données de marché : timeout, retry, cache."""

import io
import logging
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from quantlab.errors import MarketDataError

log = logging.getLogger(__name__)

ECB_BASE = "https://data-api.ecb.europa.eu/service/data"
RETRY_STATUS = {429, 500, 502, 503, 504}


class MarketDataLoader:
    def __init__(
        self, cache_dir="data/cache", base_url=ECB_BASE, timeout=10.0, retries=3, backoff=1.0, session=None
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.session = session or requests.Session()

    def _get(self, url, params):
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code in RETRY_STATUS:
                    raise requests.HTTPError(f"{resp.status_code} temporaire", response=resp)
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status not in RETRY_STATUS:
                    raise MarketDataError(f"Requête refusée ({status}) : {url}") from e
                last_error = e
            except (requests.Timeout, requests.ConnectionError) as e:
                last_error = e
            log.warning(
                "Tentative %d/%d échouée : %s %s",
                attempt,
                self.retries,
                type(last_error).__name__,
                last_error,
            )
            if attempt < self.retries:
                time.sleep(self.backoff * 2 ** (attempt - 1))
        raise MarketDataError(f"Source indisponible après {self.retries} tentatives : {url}") from last_error

    def _cache_path(self, flow, key):
        return self.cache_dir / f"{flow}_{key}.csv"

    def ecb_series(self, flow, key, start="2016-01-01", use_cache_today=True):
        """Série BCE (index date, valeurs float). Cache disque ; repli sur le cache si l'API échoue."""
        path = self._cache_path(flow, key)
        if use_cache_today and path.exists() and date.fromtimestamp(path.stat().st_mtime) == date.today():
            return self._read_cache(path)
        try:
            resp = self._get(f"{self.base_url}/{flow}/{key}", {"startPeriod": start, "format": "csvdata"})
        except MarketDataError:
            if path.exists():
                log.warning(
                    "API indisponible : utilisation du cache du %s pour %s",
                    date.fromtimestamp(path.stat().st_mtime),
                    key,
                )
                return self._read_cache(path)
            raise
        series = self._parse_csv(resp.text, name=key)
        series.to_csv(path)
        return series

    @staticmethod
    def _parse_csv(text, name):
        df = pd.read_csv(
            io.StringIO(text),
            usecols=["TIME_PERIOD", "OBS_VALUE"],
            parse_dates=["TIME_PERIOD"],
            index_col="TIME_PERIOD",
        )
        s = pd.to_numeric(df["OBS_VALUE"], errors="coerce").dropna().sort_index()
        if s.empty:
            raise MarketDataError(f"Aucune observation pour {name}")
        s.index.name = "date"
        return s.rename(name)

    @staticmethod
    def _read_cache(path):
        s = pd.read_csv(path, parse_dates=["date"], index_col="date").iloc[:, 0]
        return s
