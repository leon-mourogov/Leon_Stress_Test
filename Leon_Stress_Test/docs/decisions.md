# Décisions techniques

Une ligne par décision : le choix, la raison, l'alternative écartée.

| Décision | Pourquoi | Écarté |
|---|---|---|
| `MarketData` immuable (`frozen=True`, `MappingProxyType`) | Un choc crée un nouveau marché : impossible de polluer le marché de base pendant un stress | Dictionnaire modifié puis restauré |
| Erreurs métier = sous-classes de `QuantLabError` | Le pipeline distingue erreur de données (message, code 2) et bug (trace) | `ValueError` partout |
| Greeks par différences finies dans la classe de base | Tout nouveau produit a des Greeks sans code supplémentaire | Greeks analytiques par produit (gardés pour les vanilles) |
| Registre `PRODUCTS` + `build(spec)` | Ajouter un produit = une classe + une ligne | `if/elif` sur le type dans le moteur |
| Validation contre QuantLib, pas QuantLib en production | Garder un code qu'on comprend entièrement ; QuantLib sert de référence | Tout en QuantLib |
| Stress en revalorisation complète | Sur un put vendu choqué de −30 %, l'approximation delta-gamma sous-estime la perte de 10 % (et la surestime au-delà de −43 %) | Sensibilités seules |
| VaR historique 500 jours, ES 97,5 % | Pas d'hypothèse de distribution ; ES exigée par la FRTB | VaR paramétrique |
| Signal décalé d'un jour, coûts inclus, walk-forward | Éviter le look-ahead bias et la sur-optimisation | Backtest sur toute la période |
| SQLite via SQLAlchemy | Un fichier, zéro serveur ; changer d'URL suffit pour PostgreSQL | CSV, PostgreSQL dès le départ |
| Configuration YAML validée par pydantic | Une vol saisie en % est refusée au chargement, pas découverte dans le rapport | Constantes dans le code |
| Étapes bloquantes / non bloquantes, codes 0/1/2 | Un rapport sans VaR vaut mieux que pas de rapport | Tout ou rien |
| Points de sauvegarde sur les étapes coûteuses | Relancer après un crash ne refait pas 40 s de calcul | Tout recalculer |
| GitHub Actions pour la planification | Le rapport tourne PC éteint, journal et artefacts gratuits | cron sur un portable |
| Streamlit pour l'interface | Une personne, quelques jours, code lisible par un quant | Dash (plus de contrôle, plus de code), React (autre équipe) |
| `services.py` entre interfaces et cœur | App, API et pipeline donnent le même prix | Calcul dans les pages |
| Données de démo synthétiques versionnées (`demo/`) | L'app en ligne et le workflow quotidien fonctionnent sur un dépôt propre | Versionner `data/` ou la base |
| Autocall en Monte Carlo à graine fixe, observations exactes | Greeks stables (nombres aléatoires communs) ; pas d'erreur de discrétisation | Graine aléatoire ; pas quotidien |
| Réduction du nombre de chemins dans la VaR pour tout produit ayant `n_paths` | Un produit Monte Carlo ajouté ne ralentit pas le rapport | `isinstance(BarrierOption)` |
| Contrôle de complétude du marché dans `step_market` | L'erreur est signalée là où on sait l'expliquer (sous-jacent, positions) | `KeyError` dans la valorisation |
| Heartbeat GitHub par l'historique des workflows | Sur GitHub, la base SQLite n'existe plus d'une exécution à l'autre | `watchdog.py` sur GitHub |
| Versions exactes dans `constraints.txt`, CI sous Windows, macOS et Linux | Le projet doit s'installer à l'identique chez n'importe qui, et le rester | Dépendances sans version ; CI sous Linux seulement |
| Données de démo prolongées jusqu'au jour J dans le workflow quotidien (même graine) | Sans cela, l'historique s'arrête au 31/12/2025 et la VaR est refusée chaque matin | Commiter des données chaque jour |
| Un importateur unique pour tous les fichiers de prix (CSV, Excel, formats large et long) | Les données arrivent d'Excel, de terminaux ou d'API dans des formats variés ; le reste du code ne voit qu'un format | Un lecteur par fichier |
| Chaque correction de l'importateur consignée dans un rapport d'import | Un nettoyage silencieux cache des problèmes de données | Corriger sans le dire |
| Erreur de saisie = saut de plus de 20 % immédiatement inversé | Attrape les x10 / ÷10 sans jamais effacer un vrai krach | Seuil bas (5 %) ou en écarts-types |
| Facteur sans historique propre : proxy déclaré dans la configuration (`risk.factor_series`) | L'hypothèse (S&P 500 pour l'Euro Stoxx 50) est explicite et modifiable | Correspondance codée en dur |
