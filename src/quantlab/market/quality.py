"""quality.py — contrôles qualité d'une série de prix."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Issue:
    severity: str  # "BLOQUANT" ou "ALERTE"
    check: str
    detail: str


class DataQualityChecker:
    def __init__(self, max_gap_days=5, max_stale_days=3, z_threshold=6.0, window=60, min_move=0.01):
        self.max_gap_days = max_gap_days
        self.max_stale_days = max_stale_days
        self.z_threshold = z_threshold
        self.window = window
        self.min_move = min_move  # plancher absolu : 1 % par défaut

    def check(self, s: pd.Series, as_of=None) -> list:
        issues = []
        name = s.name or "série"
        if s.empty:
            return [Issue("BLOQUANT", "vide", f"{name} : aucune observation")]
        if not s.index.is_monotonic_increasing:
            issues.append(Issue("BLOQUANT", "ordre", f"{name} : dates non triées"))
        if s.index.has_duplicates:
            issues.append(
                Issue("BLOQUANT", "doublons", f"{name} : {int(s.index.duplicated().sum())} date(s) en double")
            )
        n_nan = int(s.isna().sum())
        if n_nan:
            issues.append(Issue("ALERTE", "manquants", f"{name} : {n_nan} valeur(s) manquante(s)"))
        n_neg = int((s <= 0).sum())
        if n_neg:
            issues.append(Issue("BLOQUANT", "positivité", f"{name} : {n_neg} valeur(s) ≤ 0"))
        gaps = s.index.to_series().diff().dt.days
        big = gaps[gaps > self.max_gap_days]
        for d, g in big.items():
            issues.append(Issue("ALERTE", "trou", f"{name} : {int(g)} jours sans donnée avant le {d.date()}"))
        if as_of is not None:
            age = int(np.busday_count(s.index.max().date(), pd.Timestamp(as_of).date()))
            if age > self.max_stale_days:
                issues.append(
                    Issue("BLOQUANT", "fraîcheur", f"{name} : dernière donnée il y a {age} jours ouvrés")
                )
        r = s.pct_change()
        vol = r.rolling(self.window, min_periods=20).std().shift(1)
        z = (r / vol).abs()
        suspicious = (z > self.z_threshold) & (r.abs() > self.min_move)
        for d, v in z[suspicious].items():
            issues.append(
                Issue(
                    "ALERTE",
                    "saut",
                    f"{name} : variation de {r[d]:+.2%} le {d.date()} ({v:.1f} écarts-types)",
                )
            )
        return issues
