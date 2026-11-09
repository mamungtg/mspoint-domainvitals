import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.domains.models import Domain

from .models import MonitoredHost, SslScan
from .services import ensure_default_hosts, execute, queue

log = logging.getLogger(__name__)
INTERVAL = timedelta(hours=24)


@shared_task(acks_late=True, soft_time_limit=60, time_limit=90)
def scan_tls_host(scan_id):
    execute(scan_id)


@shared_task
def schedule_due_tls_scans():
    """Queue a certificate check for every enabled host on a verified domain
    that has not been checked in the last 24 hours."""
    for d in Domain.objects.filter(verified_at__isnull=False, organization__is_demo=False, tls_hosts__isnull=True):
        ensure_default_hosts(d)
    cutoff = timezone.now() - INTERVAL
    due = (
        MonitoredHost.objects.filter(
            enabled=True,
            domain__verified_at__isnull=False,
            domain__organization__is_demo=False,
            domain__organization__status="active",
        )
        .filter(Q(latest_scan__isnull=True) | Q(latest_scan__created_at__lt=cutoff))
        .exclude(scans__status=SslScan.Status.QUEUED)
    )
    n = 0
    for host in due.iterator():
        s = queue(host, trigger="schedule")
        scan_tls_host.delay(str(s.pk))
        n += 1
    log.info("queued %s TLS scans", n)
    return n
