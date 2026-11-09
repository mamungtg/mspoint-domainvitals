from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.dns_monitor.checks.base import WARNING, CheckResult

from . import scanner
from .evaluate import evaluate
from .models import MonitoredHost, SslScan

log = logging.getLogger(__name__)


def default_hostnames(domain_name: str) -> list[str]:
    return [domain_name, f"www.{domain_name}"]


def ensure_default_hosts(domain) -> None:
    if domain.tls_hosts.exists():
        return
    for h in default_hostnames(domain.name):
        MonitoredHost.objects.get_or_create(domain=domain, hostname=h, port=443)


def in_scope(hostname: str, domain_name: str) -> bool:
    h = hostname.lower().rstrip(".")
    return h == domain_name or h.endswith("." + domain_name)


def store_result(scan: SslScan, info: dict | None, result: CheckResult | None, error: str = "") -> SslScan:
    with transaction.atomic():
        scan.completed_at = timezone.now()
        if info is None:
            scan.status, scan.result_status, scan.error = SslScan.Status.FAILED, "error", error[:255]
            scan.findings = [
                {
                    "code": "tls_unreachable",
                    "severity": WARNING,
                    "title": "Could not check the certificate",
                    "detail": error,
                    "fix": "Make sure the host name resolves to a public server that accepts HTTPS on this port.",
                }
            ]
        else:
            scan.status = SslScan.Status.COMPLETED
            scan.result_status = result.status
            scan.certificate = info
            scan.findings = [f.__dict__ for f in result.findings]
            scan.not_after = info.get("not_after") or None
        scan.save()
        MonitoredHost.objects.filter(pk=scan.host_id).update(latest_scan=scan)
    return scan


def execute(scan_id, *, scan_fn=scanner.scan) -> SslScan | None:
    scan = (
        SslScan.objects.select_related("host", "host__domain", "host__domain__organization").filter(pk=scan_id).first()
    )
    if scan is None or scan.status != SslScan.Status.QUEUED:
        return scan
    host = scan.host
    if not host.domain.is_verified or host.domain.organization.is_demo or not in_scope(host.hostname, host.domain.name):
        return store_result(scan, None, None, "Domain is not verified")
    try:
        info = scan_fn(host.hostname, host.port).to_dict()
    except (scanner.ScanBlocked, scanner.ScanFailed) as exc:
        return store_result(scan, None, None, str(exc))
    except Exception as exc:  # never leave a scan queued forever
        log.exception("tls scan %s failed", scan_id)
        return store_result(scan, None, None, f"Unexpected error ({exc.__class__.__name__})")
    return store_result(scan, info, evaluate(info, timezone.now()))


def active_scan(host) -> SslScan | None:
    return host.scans.filter(status=SslScan.Status.QUEUED).first()


def queue(host, trigger="manual") -> SslScan:
    return SslScan.objects.create(host=host, trigger=trigger, created_at=timezone.now())
