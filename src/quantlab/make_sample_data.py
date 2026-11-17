"""make_sample_data.py — données de marché synthétiques et reproductibles (démonstration et tests)."""

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar


def make_sample_data(folder="data", seed=2287, end="2025-12-31"):
    """Écrit fx.csv et spx.csv dans `folder`. `end="today"` prolonge la série jusqu'à aujourd'hui :
    même graine, donc l'historique jusqu'au 31/12/2025 est identique et seuls des jours sont ajoutés."""
    if end == "today":
        end = pd.Timestamp.today().normalize()
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2016-01-04", end)  # jours ouvrés lundi-vendredi
    n = len(dates)
    vols = np.array([0.07, 0.09, 0.17]) / np.sqrt(252)  # EURUSD, USDJPY, S&P 500 (par jour)
    corr = np.array([[1.0, -0.3, 0.2], [-0.3, 1.0, 0.3], [0.2, 0.3, 1.0]])
    z = rng.standard_normal((n, 3)) @ np.linalg.cholesky(corr).T  # chocs corrélés
    stress = (dates >= "2020-02-20") & (dates <= "2020-04-30")  # régime de crise
    scale = np.where(stress[:, None], 3.0, 1.0)
    drift = np.array([0.0, 0.0001, 0.0003])
    drift = np.where(stress[:, None], [0.0, -0.0005, -0.004], drift)
    log_ret = drift + vols * scale * z
    start = np.array([1.0850, 118.50, 2010.0])
    prices = start * np.exp(np.cumsum(log_ret, axis=0))
    df = pd.DataFrame(prices, index=dates, columns=["EURUSD", "USDJPY", "SPX"]).round(
        {"EURUSD": 4, "USDJPY": 2, "SPX": 2}
    )

    Path(folder).mkdir(parents=True, exist_ok=True)
    fx = df[["EURUSD", "USDJPY"]].copy()
    fx.index.name = "date"
    fx = fx.astype(object)
    fx.iloc[100, 0] = np.nan  # cotation manquante
    fx.iloc[500, 1] = "-"  # tiret au lieu d un nombre
    fx.iloc[900, 0] = fx.iloc[900, 0] * 10  # erreur de saisie (×10)
    fx = pd.concat([fx, fx.iloc[[1500]]]).sort_index()  # ligne dupliquée
    fx.to_csv(Path(folder) / "fx.csv")

    holidays = USFederalHolidayCalendar().holidays(dates[0], dates[-1])
    spx = df.loc[~df.index.isin(holidays), ["SPX"]].rename(columns={"SPX": "close"})
    spx.index.name = "date"
    spx.to_csv(Path(folder) / "spx.csv")
    return df


if __name__ == "__main__":
    import sys

    # python -m quantlab.make_sample_data [dossier] [date de fin | today]
    folder = sys.argv[1] if len(sys.argv) > 1 else "data"
    end = sys.argv[2] if len(sys.argv) > 2 else "2025-12-31"
    df = make_sample_data(folder, end=end)
    first, last = df.index[0], df.index[-1]
    print(f"Fichiers créés dans {folder}/ : fx.csv, spx.csv ({first:%Y-%m-%d} -> {last:%Y-%m-%d})")
