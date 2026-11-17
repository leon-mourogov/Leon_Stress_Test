# Architecture

## Principe

Le calcul vit dans le paquet `quantlab` ; les interfaces (app, API, pipeline) ne font qu'appeler et afficher.
Conséquence vérifiée par les tests : le même produit a le même prix dans l'app, dans l'API et dans le rapport.

## Modules

| Module | Responsabilité | Classes / fonctions principales |
|---|---|---|
| `market/importer.py` | Lecture de tout fichier de prix (CSV, Excel) vers un format unique, avec rapport d'import | `read_price_file`, `load_price_files`, `ImportReport` |
| `market/` (autres) | Données de marché : contrôles qualité, objets immuables, téléchargement | `MarketData`, `YieldCurve`, `MarketDataLoader`, `DataQualityChecker` |
| `pricing/` | Valorisation et Greeks | `Instrument` (abstraite), 7 produits, `PRODUCTS`, `build(spec)` |
| `risk/` | Book, stress, VaR, attribution de P&L | `Position`, `load_book`, `Scenario`, `run_stress`, `var_es`, `taylor_pnl` |
| `backtest/` | Stratégies, moteur, métriques, walk-forward | `Strategy`, `SMACross`, `run_backtest`, `grid_search` |
| `storage.py` | Base SQLite : prix, métriques, exécutions | `upsert_prices`, `save_metrics`, `log_run`, `last_runs` |
| `config.py` | Configuration YAML validée (pydantic) | `Settings`, `load_settings` |
| `services.py` | Fonctions appelées par l'app et l'API, avec les unités d'affichage | `price`, `spot_vol_grid`, `stress_table`, `to_excel_bytes` |
| `pipelines/` | Orchestration du rapport quotidien, codes de sortie, supervision | `run_daily`, `STEPS`, `watchdog` |
| `reporting/` | Mise en forme uniquement | `write_excel`, `write_pdf` |
| `app/` | Application Streamlit (Pricer, Import, Stress, Backtest, Rapports, Comparer), aucun calcul | — |
| `api.py` | API HTTP/JSON | `POST /price`, `GET /health` |

## Règles de dépendance

- `pricing` ne connaît que `market`. `risk` connaît `pricing` et `market`. Rien dans le cœur ne connaît
  Streamlit, FastAPI, SQLite ou le format des rapports.
- Les erreurs du paquet sont des sous-classes de `QuantLabError` (`MarketDataError`, `DataQualityError`,
  `ConfigError`, `PricingError`) : le pipeline sait ce qui est une erreur de données (message clair, code 2)
  et ce qui est un bug (trace complète).
- Tout fichier de prix passe par `market/importer.py` : le reste du code ne voit qu'un DataFrame (index de dates
  trié, une colonne par série). Les facteurs du book sont reliés aux séries par leur nom ou par un proxy déclaré
  dans `risk.factor_series`.

## Le pipeline quotidien

| Étape | Bloquante | Point de sauvegarde |
|---|---|---|
| inputs (book, scénarios, limites) | oui | non |
| market (instantané + contrôle de complétude) | oui | non |
| history (fichiers de prix → importateur → base → lecture) | non | non |
| valuation | oui | oui |
| stress | oui | oui |
| var | non | oui |
| limits | oui | non |
| archive (métriques en base) | oui | non |
| report (Excel + PDF) | oui | non |

Codes de sortie : 0 = OK, 1 = rapport incomplet (une étape non bloquante a échoué), 2 = échec.
Chaque exécution est enregistrée dans la table `runs`. Une étape non bloquante en échec donne un rapport
partiel plutôt que pas de rapport.

## Planification et supervision

- `daily.yml` : du lundi au vendredi à 7 h 30, heure de Paris, sur GitHub Actions ; rapport en artefact.
- `heartbeat.yml` : à 8 h 30, échoue (et GitHub notifie) si aucune exécution réussie de `daily.yml` aujourd'hui.
- En local : `scripts/run_daily.sh` par cron, et `python -m quantlab.pipelines.watchdog` à 8 h 30, qui lit la
  table `runs`.

## Configurations

| Fichier | Usage |
|---|---|
| `config/settings.yaml` | Développement local, données dans `data/` (non versionnées) |
| `config/settings_demo.yaml` | GitHub Actions et Streamlit Community Cloud, données synthétiques versionnées dans `demo/` |

L'app lit `settings_demo.yaml` par défaut ; la variable d'environnement `QUANTLAB_SETTINGS` en choisit une autre.
Les secrets (mot de passe SMTP) ne sont jamais dans un fichier versionné : variable d'environnement
`QUANTLAB_SMTP_PASSWORD`, secrets GitHub, secrets Streamlit.
