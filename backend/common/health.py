"""Heartbeats for background work, read by the health endpoints.

Each job records when it last finished successfully. The deep health check
reports a job as stale when that is longer ago than its allowed age, which is
how an external uptime monitor learns that Celery beat, the worker or the DMARC
mailbox has stopped, even though the website itself still answers.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache

PREFIX = "health:last:"
# name -> seconds after which the job counts as stale
MAX_AGE = {
    "scheduler": 15 * 60,  # heartbeat runs every 5 minutes (beat -> worker)
    "dmarc_mailbox": 60 * 60,  # polled every 10 minutes
}


def mark(name: str) -> None:
    cache.set(PREFIX + name, time.time(), timeout=7 * 24 * 3600)


def status(name: str) -> dict:
    """{"status": "ok" | "stale" | "missing" | "disabled", "age": seconds or None}."""
    if name == "dmarc_mailbox" and not settings.DMARC_IMAP_HOST:
        return {"status": "disabled", "age": None}
    last = cache.get(PREFIX + name)
    if last is None:
        return {"status": "missing", "age": None}
    age = int(time.time() - float(last))
    return {"status": "ok" if age <= MAX_AGE[name] else "stale", "age": age}
