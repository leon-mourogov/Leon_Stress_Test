# Guide d'utilisation

> Toutes les données fournies sont **synthétiques** (simulées avec une graine fixe). Aucun chiffre ne décrit
> un marché réel.

## 1. Installation

Python 3.11 à 3.14 (testé sous Windows, macOS Intel et Apple Silicon, Linux). Depuis le dossier du projet :

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" -c constraints.txt
```

**Windows (PowerShell)**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1     # si refusé : Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e ".[dev]" -c constraints.txt
```

- `.venv` isole les bibliothèques du projet ; l'activer dans chaque nouveau terminal.
- `[dev]` ajoute les outils de test, Streamlit, FastAPI et QuantLib (référence de validation).
- `-c constraints.txt` installe les versions exactes avec lesquelles le projet est testé.

Vérification : `pytest -m "not slow"`.

## 2. Rapport de risque

```bash
python -m quantlab.pipelines.run_daily --config config/settings_demo.yaml --date 2025-12-31
```

Résultat dans `demo/reports/2025-12-31/` : un classeur Excel (Synthèse, Limites, Positions, Stress, VaR) et un
PDF de 2 pages, en 30 à 45 s.

| Code de sortie | Statut | Signification |
|---|---|---|
| 0 | OK | Rapport complet |
| 1 | INCOMPLET | Une étape non bloquante a échoué (ex. VaR sans historique suffisant) ; le rapport est produit |
| 2 | ÉCHEC | Donnée invalide ou erreur bloquante ; cause dans le terminal, le journal et l'alerte |

- Relancer la même date ne refait rien ; `--force` recalcule.
- Sans `--date` : jour ouvré précédent. Les données de démonstration s'arrêtent au 31/12/2025 ; pour une date
  plus récente, les prolonger : `python -m quantlab.make_sample_data demo today`.

## 3. Importer ses propres données (CSV ou Excel)

### Voir ce que contient un fichier

```bash
python -m quantlab.market.importer mes_prix.xlsx autre_export.csv
```

Affiche ce qui a été reconnu (séparateur, format de date, séries, plage de dates) et chaque correction
appliquée, sans lancer de calcul. `--save prix.csv` enregistre les données nettoyées.

### Rapport complet sur ces données

```bash
python -m quantlab.pipelines.run_daily --config config/settings_demo.yaml --prices mes_prix.xlsx
```

Les fichiers de `--prices` remplacent ceux de la configuration ; la date du rapport devient leur dernière date
commune (modifiable avec `--date`). Pour les utiliser en permanence : les lister dans `paths.prices` du fichier
de configuration.

### Depuis l'application

Page **Import** : déposer un ou plusieurs fichiers, lire ce qui a été compris, puis :
- **Utiliser ces données dans l'application** : la page Backtest travaille sur les séries importées ;
- **Lancer le rapport** : stress, VaR, ES et limites sur ces données, avec téléchargement Excel et PDF.

### Formats reconnus automatiquement

| Élément | Reconnu |
|---|---|
| Fichier | `.csv`, `.txt`, `.xlsx` |
| Séparateur | `,` `;` tabulation `\|` |
| Encodage | UTF-8 (avec ou sans BOM), Windows-1252 |
| Nombres | `1234.5`, `1 234,5`, `1.234,5` (virgule décimale des exports Excel français) |
| Dates | `2025-12-31`, `31/12/2025`, `12/31/2025`, `31.12.2025`, `20251231`, cellules date d'Excel ; dates ambiguës lues en jour/mois et signalées |
| Disposition | une colonne par série, ou trois colonnes `date, série, valeur` |
| Noms | `EUR/USD`, `EURUSD=X` → `EURUSD` ; `^GSPC`, `S&P 500` → `SPX` ; `Euro Stoxx 50` → `SX5E` ; une colonne unique `Close` prend le nom du fichier |

Nettoyage, toujours consigné : lignes sans valeur (pieds de page) et colonnes de texte retirées, doublons de
dates supprimés, erreur de saisie isolée (saut de plus de 20 % immédiatement inversé) masquée sans toucher à un
vrai krach, trou d'un jour comblé par le prix précédent.

Refus avec un message explicite (code 2) : dates illisibles, aucune colonne numérique, prix négatifs ou nuls,
même série dans deux fichiers, fichier introuvable.

### Facteurs de risque et proxys

Le book porte sur `SX5E` et `EURUSD`. Pour la VaR, chaque facteur prend la série de même nom ; à défaut, celle
déclarée dans `risk.factor_series` (par défaut `SX5E: SPX` : le S&P 500 sert de proxy à l'Euro Stoxx 50). Un
fichier contenant l'Euro Stoxx 50 est utilisé directement. Un facteur sans série ni proxy rend le rapport
INCOMPLET avec un message qui le nomme.

## 4. Application web

```bash
streamlit run app/Pricer.py
```

http://localhost:8501 :

| Page | Contenu |
|---|---|
| Pricer | Prix, delta cash, vega, payoff et grille spot × vol de chaque produit ; panier de produits |
| Import | Import de fichiers de prix et rapport de risque à la demande |
| Stress | Book sous la bibliothèque de scénarios ; scénario composé avec des curseurs ; export Excel |
| Backtest | Carte des ratios de Sharpe des moyennes mobiles, courbes de valeur |
| Rapports | Historique des rapports, VaR sur 30 jours, téléchargement des fichiers |
| Comparer | Deux produits côte à côte |

Par défaut l'application lit `config/settings_demo.yaml`. Avec une autre configuration :
`QUANTLAB_SETTINGS=config/settings.yaml streamlit run app/Pricer.py`.

## 5. API

```bash
uvicorn quantlab.api:app
```

Documentation interactive sur http://127.0.0.1:8000/docs.

```python
import requests
r = requests.post("http://127.0.0.1:8000/price", json={"product": {"K": 5000, "T": 1, "notional": 200}})
print(r.json()["valeur"])   # 55635.9...
```

## 6. Utiliser le code depuis Python

```python
from quantlab.pricing.instruments import build
from quantlab.services import make_market, price

md = make_market(spot=4900, vol=0.20)
print(price({"type": "european", "underlying": "SX5E", "K": 5000, "T": 1.0, "notional": 200}, md))

autocall = build({"type": "autocall", "underlying": "SX5E", "T": 5, "S0": 4900.0,
                  "coupon": 0.07, "notional": 1_000_000})
print(autocall.value(md), autocall.scenarios(md))
```

## 7. Modifier les entrées

| Objet | Fichier |
|---|---|
| Positions du book | `config/book.json` |
| Scénarios de stress | `config/scenarios.json` (spot en relatif, vol en absolu, taux en points de base) |
| Limites de risque | `config/limits.json` |
| Fichiers de prix, marché du jour, VaR, alertes | `config/settings.yaml` / `config/settings_demo.yaml` |
| Lots de backtests | `config/experiments.json` |

Tout est validé au chargement : une volatilité saisie en pourcentage ou un trade incomplet est refusé avec un
message précis (`ConfigError : book.json, trade n°3 : ...`).

**Alertes e-mail** : désactivées par défaut. Les activer dans la configuration (`alerts`), le mot de passe SMTP
étant lu dans la variable d'environnement `QUANTLAB_SMTP_PASSWORD` (jamais dans un fichier versionné).

## 8. Ajouter un produit

1. Dans `src/quantlab/pricing/instruments.py`, une classe qui hérite d'`Instrument` et définit `unit_price(md)`
   (prix pour 1 de notionnel) et `payoff(ST)`.
2. Une ligne dans `PRODUCTS`.
3. Des tests, dont au moins un cas limite à prix connu (exemple : `tests/test_autocall.py`).

Greeks, stress, VaR, rapport, application et API le prennent en charge sans autre modification.

## 9. Planification

- **GitHub Actions** : `.github/workflows/daily.yml` produit le rapport du lundi au vendredi à 7 h 30 (heure de
  Paris) et `heartbeat.yml` vérifie à 8 h 30 qu'il a réussi ; rapports téléchargeables dans l'onglet *Actions*.
- **cron (macOS / Linux)** : `30 7 * * 1-5 /chemin/vers/quantlab/scripts/run_daily.sh`.
- **Planificateur de tâches (Windows)** : tâche hebdomadaire du lundi au vendredi à 7 h 30 lançant
  `scripts\run_daily.bat`.
- **APScheduler** : `pip install -e ".[scheduler]" -c constraints.txt`, puis `python -m quantlab.pipelines.scheduler`.

## 10. Problèmes fréquents

| Message | Cause | Solution |
|---|---|---|
| `python` « n'est pas reconnu » (Windows) | « Add python.exe to PATH » non coché à l'installation | Réinstaller Python en cochant la case |
| `command not found: python` (macOS) | La commande est `python3` | Utiliser `python3` pour créer `.venv` |
| `No module named 'quantlab'` | Environnement non activé | Activer `.venv`, puis réinstaller (section 1) |
| Rapport INCOMPLET « Historique de prix arrêté au … » | Pas de prix récents pour la date demandée | `--date` dans la plage des données, ou prolonger les données (section 2) |
| Rapport INCOMPLET « Pas d'historique pour ['SX5E'] » | Facteur du book sans série ni proxy | Ajouter un fichier qui le contient, ou un proxy dans `risk.factor_series` |
| ÉCHEC « dates illisibles » | Format de date inconnu | `python -m quantlab.market.importer fichier` pour voir ce qui est lu |
| Le rapport ne se refait pas | Il existe déjà pour cette date | `--force` |
| Page Rapports vide | Aucun rapport en base | Lancer un rapport (section 2) |
