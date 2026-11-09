from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from .changes import diff_records
from .checks import run_checks
from .models import DnsChange, DnsScan
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


def record_changes(scan: DnsScan) -> list[DnsChange]:
    """Store differences against the previous completed scan with a full inventory.
    The first scan of a domain is the baseline and produces no changes."""
    prev = (
        DnsScan.objects.filter(
            domain_id=scan.domain_id, status=DnsScan.Status.COMPLETED, created_at__lt=scan.created_at
        )
        .exclude(pk=scan.pk)
        .exclude(records={})
        .order_by("-created_at")
        .first()
    )
    if prev is None or not scan.records:
        return []
    when = scan.completed_at or timezone.now()
    rows = [
        DnsChange(domain_id=scan.domain_id, scan=scan, detected_at=when, **c)
        for c in diff_records(prev.records, scan.records)
    ]
    return DnsChange.objects.bulk_create(rows)


def execute_scan(scan: DnsScan, resolver: BaseResolver | None = None, when=None) -> DnsScan:
    domain = scan.domain
    scan.status = DnsScan.Status.RUNNING
    scan.started_at = when or timezone.now()
    scan.save(update_fields=["status", "started_at"])
    try:
        hosts = [f"www.{domain.name}"] + [h for h in (domain.dns_watch_names or []) if h != f"www.{domain.name}"]
        out = run_checks(domain.name, resolver or resolver_for(domain), domain.dkim_selectors, hosts=hosts)
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
    dns_result = out["results"].get("dns", {})
    scan.records = dns_result.get("data", {}).pop("records", {}) if dns_result else {}
    scan.results = out["results"]
    scan.completed_at = when or timezone.now()
    with transaction.atomic():
        scan.save()
        if dns_result and dns_result.get("status") != "error":
            record_changes(scan)
    latest = domain.latest_scan
    if latest is None or latest.created_at <= scan.created_at:
        type(domain).objects.filter(pk=domain.pk).update(latest_scan=scan)
        domain.latest_scan = scan
    return scan
