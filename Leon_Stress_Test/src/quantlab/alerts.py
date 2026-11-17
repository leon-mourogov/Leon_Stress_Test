"""alerts.py — alerte email quand le rapport n'est pas sorti complet."""

import logging
import os
import smtplib
from email.message import EmailMessage

from quantlab.errors import ConfigError

log = logging.getLogger(__name__)


def build_message(alerts, subject, body):
    msg = EmailMessage()
    msg["From"] = alerts.sender
    msg["To"] = ", ".join(alerts.recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def send_alert(alerts, subject, body, smtp_factory=smtplib.SMTP):
    """Envoie l'alerte. Ne lève jamais : une alerte qui plante ne doit pas masquer l'erreur d'origine."""
    if not alerts.enabled:
        log.info("Alertes désactivées : %s", subject)
        return False
    try:
        password = os.environ.get("QUANTLAB_SMTP_PASSWORD")
        if not password:
            raise ConfigError("Variable d'environnement QUANTLAB_SMTP_PASSWORD absente")
        with smtp_factory(alerts.smtp_host, alerts.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(alerts.sender, password)
            smtp.send_message(build_message(alerts, subject, body))
        log.info("Alerte envoyée à %s : %s", alerts.recipients, subject)
        return True
    except Exception:
        log.exception("Impossible d'envoyer l'alerte « %s »", subject)
        return False
