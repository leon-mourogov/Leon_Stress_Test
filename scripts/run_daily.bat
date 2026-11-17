@echo off
REM run_daily.bat - lance le rapport quotidien sous Windows (Planificateur de taches).
REM Equivalent de scripts/run_daily.sh pour macOS et Linux.
REM Le Planificateur lance les programmes sans ton dossier courant ni ton environnement virtuel :
REM on se place a la racine du projet et on active .venv avant tout.
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
REM Secrets (QUANTLAB_SMTP_PASSWORD) : variable d'environnement utilisateur, creee une fois avec
REM   setx QUANTLAB_SMTP_PASSWORD "mot-de-passe"
python -m quantlab.pipelines.run_daily --config config\settings.yaml %*
exit /b %ERRORLEVEL%
