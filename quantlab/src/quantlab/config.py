"""config.py — lecture et validation de settings.yaml."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from quantlab.errors import ConfigError


class Paths(BaseModel):
    book: Path
    scenarios: Path
    limits: Path
    prices: list[Path] = Field(min_length=1)  # un ou plusieurs fichiers CSV / Excel
    reports: Path
    logs: Path


class Database(BaseModel):
    url: str


class Risk(BaseModel):
    base_currency: str = "EUR"
    var_window_days: int = Field(500, ge=100)
    var_level: float = Field(0.99, gt=0.5, lt=1)
    es_level: float = Field(0.975, gt=0.5, lt=1)
    mc_paths_var: int = Field(10_000, ge=1_000)
    # série historique utilisée pour un facteur absent des fichiers de prix (proxy), ex. {SX5E: SPX}
    factor_series: dict[str, str] = {}


class Market(BaseModel):
    spots: dict[str, float]
    vols: dict[str, float]
    rates: dict[str, float]
    div_yields: dict[str, float] = {}

    @field_validator("vols")
    @classmethod
    def vols_in_decimal(cls, v):
        bad = {k: x for k, x in v.items() if not 0 < x < 3}
        if bad:
            raise ValueError(f"vols hors bornes (décimal attendu) : {bad}")
        return v


class Alerts(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    sender: str = ""
    recipients: list[str] = []


class Settings(BaseModel):
    paths: Paths
    database: Database
    risk: Risk = Risk()
    market: Market
    alerts: Alerts = Alerts()


def load_settings(path) -> Settings:
    path = Path(path).resolve()
    if not path.exists():
        raise ConfigError(f"Fichier de configuration introuvable : {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        settings = Settings.model_validate(raw)
    except yaml.YAMLError as e:
        raise ConfigError(f"{path.name} : YAML invalide ({e})") from e
    except ValidationError as e:
        raise ConfigError(f"{path.name} : configuration invalide\n{e}") from e
    # chemins relatifs -> relatifs au dossier du fichier de configuration
    base = path.parent
    resolve = lambda p: p if p.is_absolute() else (base / p).resolve()  # noqa: E731
    for name, value in settings.paths:
        setattr(
            settings.paths, name, [resolve(v) for v in value] if isinstance(value, list) else resolve(value)
        )
    url = settings.database.url
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        settings.database.url = "sqlite:///" + str((base / url.removeprefix("sqlite:///")).resolve())
    return settings
