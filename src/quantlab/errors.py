"""errors.py — hiérarchie des erreurs de quantlab.

Règle : le code du package ne lève QUE des sous-classes de QuantLabError (ou des erreurs
Python standard pour les bugs de programmation). Un appelant peut ainsi tout attraper d'un coup.
"""


class QuantLabError(Exception):
    """Base de toutes les erreurs métier de quantlab."""


class MarketDataError(QuantLabError):
    """Donnée de marché introuvable ou source indisponible (réseau, API, fichier absent)."""


class DataQualityError(QuantLabError, ValueError):
    """Donnée présente mais invalide (spot négatif, vol en pourcentage...). Bloquant."""


class ConfigError(QuantLabError, ValueError):
    """Fichier de configuration absent, illisible ou incohérent."""


class PricingError(QuantLabError):
    """Le pricer ne peut pas produire de prix fiable pour ces entrées."""
