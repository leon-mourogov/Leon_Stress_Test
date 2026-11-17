"""Alertes email : testées avec un faux serveur SMTP, jamais un vrai."""

from quantlab.alerts import send_alert
from quantlab.config import Alerts

ALERTS = Alerts(enabled=True, smtp_host="smtp.test", sender="q@test", recipients=["leon@test"])


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        assert password == "secret"

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_alert_is_sent(monkeypatch):
    monkeypatch.setenv("QUANTLAB_SMTP_PASSWORD", "secret")
    FakeSMTP.sent.clear()
    assert send_alert(ALERTS, "[quantlab] ÉCHEC", "détail", smtp_factory=FakeSMTP)
    msg = FakeSMTP.sent[0]
    assert msg["To"] == "leon@test" and "ÉCHEC" in msg["Subject"]


def test_missing_password_does_not_raise(monkeypatch, caplog):
    monkeypatch.delenv("QUANTLAB_SMTP_PASSWORD", raising=False)
    assert send_alert(ALERTS, "x", "y", smtp_factory=FakeSMTP) is False
    assert "QUANTLAB_SMTP_PASSWORD" in caplog.text


def test_disabled_alerts_send_nothing():
    FakeSMTP.sent.clear()
    assert send_alert(Alerts(enabled=False), "x", "y", smtp_factory=FakeSMTP) is False
    assert FakeSMTP.sent == []
