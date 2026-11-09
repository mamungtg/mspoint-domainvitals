from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from .checks import run_checks
from .models import DnsScan
from .resolver import BaseResolver, LiveResolver

logger = logging.getLogger(__name__)


def resolver_for(domain) -> BaseResolver:
    if domain.organization.is_demo:
        from apps.domains.demo import demo_resolver

        return demo_resolver()
    return LiveResolver()


def active_scan(domain) -> DnsScan | None:
    return domain.scans.filter(status__in=[DnsScan.Status.QUEUED, DnsScan.Status.RUNNING]).first()


def queue_scan(domain, trigger=DnsScan.Trigger.MANUAL) -> DnsScan:
    """Create a queued scan and hand it to Celery after the transaction commits."""
    from .tasks import scan_domain_task

    scan = DnsScan.objects.create(domain=domain, trigger=trigger, created_at=timezone.now())
    transaction.on_commit(lambda: scan_domain_task.delay(str(scan.pk)))
    return scan


def execute_scan(scan: DnsScan, resolver: BaseResolver | None = None, when=None) -> DnsScan:
    domain = scan.domain
    scan.status = DnsScan.Status.RUNNING
    scan.started_at = when or timezone.now()
    scan.save(update_fields=["status", "started_at"])
    try:
        out = run_checks(domain.name, resolver or resolver_for(domain), domain.dkim_selectors)
    except Exception as exc:  # never leave a scan stuck in "running"
        logger.exception("scan %s failed", scan.pk)
        scan.status = DnsScan.Status.FAILED
        scan.error = str(exc)[:250]
        scan.completed_at = timezone.now()
        scan.save(update_fields=["status", "error", "completed_at"])
        return scan
    scan.status = DnsScan.Status.COMPLETED
    scan.health_score = out["score"]
    scan.overall_status = out["overall"]
    scan.critical_count = out["critical"]
    scan.warning_count = out["warning"]
    scan.summary = out["summary"]
    scan.results = out["results"]
    scan.completed_at = when or timezone.now()
    scan.save()
    latest = domain.latest_scan
    if latest is None or latest.created_at <= scan.created_at:
        type(domain).objects.filter(pk=domain.pk).update(latest_scan=scan)
        domain.latest_scan = scan
    return scan
