from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.audit.models import AuditLog

from .checks import verify_ownership
from .models import DnsScan
from .resolver import LiveResolver
from .services import active_scan, execute_scan, queue_scan


@shared_task(acks_late=True)
def scan_domain_task(scan_id: str):
    scan = DnsScan.objects.select_related("domain__organization").filter(pk=scan_id).first()
    if scan is None or scan.status != DnsScan.Status.QUEUED:
        return
    execute_scan(scan)


@shared_task
def schedule_due_scans(limit: int = 500):
    from apps.domains.models import Domain

    cutoff = timezone.now() - timedelta(hours=settings.DNS_SCAN_INTERVAL_HOURS)
    due = (
        Domain.objects.filter(
            verified_at__isnull=False,
            monitoring_enabled=True,
            organization__is_demo=False,
            organization__status="active",
        )
        .filter(Q(latest_scan__isnull=True) | Q(latest_scan__created_at__lt=cutoff))
        .select_related("organization")[:limit]
    )
    queued = 0
    for d in due:
        if active_scan(d) is None:
            queue_scan(d, DnsScan.Trigger.SCHEDULE)
            queued += 1
    return queued


@shared_task
def recheck_verifications(limit: int = 1000):
    """Domains must keep their verification record; drop monitoring after a grace period."""
    from apps.domains.models import Domain

    now = timezone.now()
    stale = Domain.objects.filter(verified_at__isnull=False, organization__is_demo=False).filter(
        Q(verification_checked_at__isnull=True) | Q(verification_checked_at__lt=now - timedelta(hours=24))
    )[:limit]
    resolver = LiveResolver()
    for d in stale:
        if verify_ownership(d.name, d.verification_token, resolver):
            d.verification_checked_at = now
            d.verification_failing_since = None
            d.save(update_fields=["verification_checked_at", "verification_failing_since"])
            continue
        d.verification_failing_since = d.verification_failing_since or now
        d.verification_checked_at = now
        fields = ["verification_checked_at", "verification_failing_since"]
        if now - d.verification_failing_since > timedelta(hours=settings.VERIFICATION_GRACE_HOURS):
            d.verified_at = None
            fields.append("verified_at")
            AuditLog.objects.create(
                organization=d.organization,
                action="domain.verification_lost",
                object_type="domains.domain",
                object_id=str(d.pk),
                metadata={"domain": d.name},
            )
        d.save(update_fields=fields)
