import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import DmarcRecord, DmarcReport
from .services import poll_mailbox
from .sources import identify

log = logging.getLogger(__name__)


@shared_task(soft_time_limit=540, time_limit=600)
def poll_dmarc_mailbox():
    result = poll_mailbox()
    if result.reports:
        from apps.alerts.tasks import process_dmarc

        ids = [str(r.pk) for r in result.reports]
        identify_sources.delay(ids)
        process_dmarc.delay(ids)


@shared_task(soft_time_limit=280, time_limit=300)
def identify_sources(report_ids):
    ips = DmarcRecord.objects.filter(report_id__in=report_ids).values_list("source_ip", flat=True).distinct()
    identify(list(ips))


@shared_task
def prune_old_reports():
    cutoff = timezone.now() - timedelta(days=settings.DMARC_RETENTION_DAYS)
    deleted, _ = DmarcReport.objects.filter(date_end__lt=cutoff).exclude(source=DmarcReport.Source.DEMO).delete()
    if deleted:
        log.info("dmarc: pruned %s rows older than %s", deleted, cutoff.date())
