import time

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from common import health
from common.tasks import heartbeat

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear():
    cache.clear()
    yield
    cache.clear()


def test_basic_health_checks_database_and_redis():
    r = APIClient().get("/api/v1/health/")
    assert r.status_code == 200
    assert r.data["checks"] == {"database": "ok", "redis": "ok"}


@override_settings(DMARC_IMAP_HOST="")
def test_deep_health_fails_until_the_scheduler_has_run():
    r = APIClient().get("/api/v1/health/deep/")
    assert r.status_code == 503 and r.data["checks"]["scheduler"] == "missing"
    assert "dmarc_mailbox" not in r.data["checks"]  # mailbox not configured

    heartbeat.delay()
    r = APIClient().get("/api/v1/health/deep/")
    assert r.status_code == 200, r.data
    assert r.data["last_run_seconds_ago"]["scheduler"] <= 1


@override_settings(DMARC_IMAP_HOST="imap.example.test")
def test_deep_health_reports_stale_jobs():
    old = time.time() - 2 * 3600
    cache.set(health.PREFIX + "scheduler", time.time())
    cache.set(health.PREFIX + "dmarc_mailbox", old)
    r = APIClient().get("/api/v1/health/deep/")
    assert r.status_code == 503
    assert r.data["checks"]["scheduler"] == "ok"
    assert r.data["checks"]["dmarc_mailbox"] == "stale"
    assert "imap" not in str(r.data)  # no internals


def test_dmarc_poll_marks_the_mailbox_healthy(monkeypatch):
    from apps.dmarc import services

    class Conn:
        def login(self, *a):
            pass

        def select(self, *a):
            pass

        def search(self, *a):
            return "OK", [b""]

        def logout(self):
            pass

    monkeypatch.setattr(services, "mailbox_configured", lambda: True)
    monkeypatch.setattr(services.imaplib, "IMAP4_SSL", lambda *a, **k: Conn())
    services.poll_mailbox()
    assert cache.get(health.PREFIX + "dmarc_mailbox")
