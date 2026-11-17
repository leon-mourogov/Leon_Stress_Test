#!/usr/bin/env bash
# run_daily.sh — lancé par cron. cron n'a ni ton PATH, ni ton dossier courant, ni ton environnement virtuel.
set -euo pipefail
cd "$(dirname "$0")/.."                       # racine du projet, quel que soit le dossier de lancement
source .venv/bin/activate                     # le Python du projet, pas celui du système
set -a; [ -f .env ] && source .env; set +a    # secrets (QUANTLAB_SMTP_PASSWORD) hors du dépôt
exec python -m quantlab.pipelines.run_daily --config config/settings.yaml "$@"
