"""Sample certificates for the demo workspace. Dates are relative to today and
refreshed daily so the sample never ages into 'everything expired'. Findings
come from the real evaluator."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .evaluate import evaluate
from .models import MonitoredHost, SslScan
from .services import store_result

LE = ("R11", "Let's Encrypt")
SECTIGO = ("Sectigo RSA Domain Validation Secure Server CA", "Sectigo Limited")
GTS = ("WR1", "Google Trust Services")

# hostname suffix -> (days left, issuer, extra fields)
PLAN = {
    "harbour-dental.example": [("", 74, LE, {}), ("www.", 74, LE, {})],
    "atlas-fitness.example": [("", 5, LE, {"hsts": None}), ("www.", 5, LE, {"hsts": None})],
    "brightpath-law.example": [
        ("", 21, SECTIGO, {}),
        (
            "www.",
            21,
            SECTIGO,
            {
                "hostname_match": False,
                "trusted": False,
                "verify_error": "Hostname mismatch, certificate is not valid for 'www.brightpath-law.example'.",
                "sans": ["brightpath-law.example"],
            },
        ),
    ],
    "greenleaf-accounting.example": [
        ("", -3, LE, {"trusted": False, "verify_error": "certificate has expired"}),
        ("www.", -3, LE, {"trusted": False, "verify_error": "certificate has expired"}),
    ],
    "northwind-logistics.example": [
        ("", 182, GTS, {"key_type": "EC", "key_bits": 256}),
        ("www.", 182, GTS, {"key_type": "EC", "key_bits": 256}),
        ("mail.", 301, SECTIGO, {"hsts": "max-age=31536000; includeSubDomains"}),
    ],
}


def _info(hostname, days, issuer, extra, now):
    end = (now + timedelta(days=days)).replace(hour=12, minute=0, second=0, microsecond=0)
    base = {
        "hostname": hostname,
        "port": 443,
        "ip": "192.0.2.10",
        "tls_version": "TLSv1.3",
        "cipher": "TLS_AES_256_GCM_SHA384",
        "subject_cn": hostname,
        "sans": [hostname],
        "issuer": issuer[0],
        "issuer_org": issuer[1],
        "serial": "4a1f9c",
        "not_before": (end - timedelta(days=90 if issuer is LE else 365)).isoformat(),
        "not_after": end.isoformat(),
        "signature_algorithm": "sha256",
        "key_type": "RSA",
        "key_bits": 2048,
        "self_signed": False,
        "trusted": True,
        "verify_error": "",
        "hostname_match": True,
        "hsts": "max-age=31536000",
    }
    base.update(extra)
    return base


def seed_demo_tls(org, *, force: bool = False) -> None:
    now = timezone.now()
    latest = SslScan.objects.filter(host__domain__organization=org).order_by("-created_at").first()
    if latest and not force and latest.created_at.date() == now.date():
        return
    with transaction.atomic():
        MonitoredHost.objects.filter(domain__organization=org).delete()
        for dom in org.domains.filter(verified_at__isnull=False):
            for prefix, days, issuer, extra in PLAN.get(dom.name, []):
                host = MonitoredHost.objects.create(domain=dom, hostname=prefix + dom.name)
                info = _info(host.hostname, days, issuer, extra, now)
                scan = SslScan.objects.create(host=host, trigger="demo", created_at=now - timedelta(minutes=20))
                store_result(scan, info, evaluate(info, now))
