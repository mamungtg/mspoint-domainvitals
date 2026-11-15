from celery import shared_task

from .models import Delivery


@shared_task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=60, time_limit=90)
def deliver(self, delivery_id):
    from .notify import deliver_now

    d = (
        Delivery.objects.select_related("channel", "channel__organization", "alert", "alert__domain")
        .filter(pk=delivery_id)
        .first()
    )
    if d is None or d.status == Delivery.Status.SENT:
        return
    d = deliver_now(d)
    if d.status == Delivery.Status.FAILED and self.request.retries < self.max_retries:
        d.status = Delivery.Status.PENDING
        d.save(update_fields=["status"])
        raise self.retry(countdown=60 * (2**self.request.retries))


@shared_task(soft_time_limit=60, time_limit=90)
def process_scan(scan_id):
    from apps.dns_monitor.models import DnsScan

    from .engine import evaluate_scan

    scan = DnsScan.objects.select_related("domain", "domain__organization").filter(pk=scan_id).first()
    if scan:
        evaluate_scan(scan)


@shared_task(soft_time_limit=60, time_limit=90)
def process_tls(scan_id):
    from apps.ssl_monitor.models import SslScan

    from .engine import evaluate_tls

    scan = (
        SslScan.objects.select_related("host", "host__domain", "host__domain__organization").filter(pk=scan_id).first()
    )
    if scan:
        evaluate_tls(scan)


@shared_task(soft_time_limit=120, time_limit=150)
def process_dmarc(report_ids):
    from .engine import evaluate_dmarc

    evaluate_dmarc(report_ids)
