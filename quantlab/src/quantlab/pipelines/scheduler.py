"""scheduler.py — planification en Python avec APScheduler (alternative à cron).

python -m quantlab.pipelines.scheduler --config config/settings.yaml
"""

import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from quantlab.pipelines.run_daily import main as run_daily_main

log = logging.getLogger("quantlab.pipelines.scheduler")

TRIGGER = CronTrigger(day_of_week="mon-fri", hour=7, minute=30, timezone="Europe/Paris")


def job(config):
    code = run_daily_main(["--config", config])  # date par défaut : jour ouvré précédent
    log.info("run_daily terminé avec le code %d", code)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/settings.yaml")
    args = p.parse_args()
    sched = BlockingScheduler()
    sched.add_job(
        job,
        TRIGGER,
        args=[args.config],
        id="run_daily",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    sched.start()  # bloque : le processus doit rester allumé


if __name__ == "__main__":
    main()
