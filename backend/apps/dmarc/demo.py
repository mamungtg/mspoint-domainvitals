"""Sample DMARC reports for the demo workspace.

Reports are keyed by domain name, and every demo workspace uses the same
made-up .example domains, so one shared set is generated and refreshed daily.
Addresses come from the documentation ranges (RFC 5737) and their sender
names are pre-filled, so no real lookups happen.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, time, timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import DmarcReport, SourceIp
from .parser import ParsedRecord, ParsedReport
from .services import store_report

DAYS = 90

# ip -> (ptr, provider)
IPS = {
    "192.0.2.41": ("mail-sor-f41.google.example", "Google"),
    "192.0.2.42": ("mail-sor-f42.google.example", "Google"),
    "198.51.100.10": ("mail-eopbgr10.outbound.protection.outlook.example", "Microsoft 365"),
    "198.51.100.11": ("mail-eopbgr11.outbound.protection.outlook.example", "Microsoft 365"),
    "198.51.100.60": ("o1.ptr60.sendgrid.example", "SendGrid"),
    "198.51.100.70": ("mail70.us4.mcsv.example", "Mailchimp"),
    "198.51.100.80": ("a8-80.smtp-out.amazonses.example", "Amazon SES"),
    "198.51.100.90": ("sender90.zoho.example", "Zoho Mail"),
    "203.0.113.200": ("", ""),
    "203.0.113.201": ("static-201.broadband.example", ""),
    "203.0.113.202": ("", ""),
}

PASS = (True, True)
DKIM_ONLY = (True, False)
SPF_ONLY = (False, True)
FAIL = (False, False)

# domain -> policy and [(ip, daily volume range, (dkim_aligned, spf_aligned), dkim signer, envelope domain)]
PLAN = {
    "harbour-dental.example": (
        {"p": "none", "pct": "100", "adkim": "r", "aspf": "r"},
        [
            ("192.0.2.41", (120, 180), PASS, "harbour-dental.example", "harbour-dental.example"),
            ("192.0.2.42", (40, 70), PASS, "harbour-dental.example", "harbour-dental.example"),
            ("198.51.100.70", (0, 260), FAIL, "mcsv.example", "mail70.mcsv.example"),
            ("203.0.113.200", (0, 12), FAIL, "", "harbour-dental.example"),
        ],
    ),
    "northwind-logistics.example": (
        {"p": "reject", "pct": "100", "adkim": "r", "aspf": "r"},
        [
            ("198.51.100.10", (300, 420), PASS, "northwind-logistics.example", "northwind-logistics.example"),
            ("198.51.100.11", (150, 220), PASS, "northwind-logistics.example", "northwind-logistics.example"),
            ("198.51.100.60", (80, 140), DKIM_ONLY, "northwind-logistics.example", "em123.sendgrid.example"),
            ("203.0.113.201", (5, 40), FAIL, "", "northwind-logistics.example"),
            ("203.0.113.202", (0, 25), FAIL, "", "northwind-logistics.example"),
        ],
    ),
    "greenleaf-accounting.example": (
        {"p": "quarantine", "pct": "50", "adkim": "r", "aspf": "r"},
        [
            ("198.51.100.10", (90, 130), PASS, "greenleaf-accounting.example", "greenleaf-accounting.example"),
            ("198.51.100.80", (20, 45), SPF_ONLY, "amazonses.example", "greenleaf-accounting.example"),
            ("198.51.100.80", (5, 15), FAIL, "amazonses.example", "bounce.amazonses.example"),
            ("203.0.113.200", (0, 8), FAIL, "", "greenleaf-accounting.example"),
        ],
    ),
    "atlas-fitness.example": (
        {"p": "reject", "pct": "100", "adkim": "r", "aspf": "r"},
        [
            ("198.51.100.90", (30, 60), PASS, "atlas-fitness.example", "atlas-fitness.example"),
        ],
    ),
}

REPORTERS = [
    ("google.com", "noreply-dmarc-support@google.com", 0.6),
    ("Outlook.com", "dmarcreport@microsoft.com", 0.3),
    ("Yahoo", "dmarchelp@yahooinc.com", 0.1),
]


def _disposition(policy: dict, passed: bool, rnd: random.Random) -> str:
    if passed or policy["p"] == "none":
        return "none"
    if rnd.randint(1, 100) > int(policy.get("pct", "100")):
        return "none"
    return policy["p"]


def _reports_for(domain: str, day, rnd: random.Random) -> list[ParsedReport]:
    policy, plan = PLAN[domain]
    begin = datetime.combine(day, time.min, tzinfo=UTC)
    end = begin + timedelta(days=1) - timedelta(seconds=1)
    out = []
    for org, addr, share in REPORTERS:
        records = []
        for ip, (lo, hi), (dkim_ok, spf_ok), signer, envelope in plan:
            n = int(rnd.randint(lo, hi) * share)
            if n <= 0:
                continue
            passed = dkim_ok or spf_ok
            records.append(
                ParsedRecord(
                    source_ip=ip,
                    count=n,
                    disposition=_disposition(policy, passed, rnd),
                    dkim_aligned=dkim_ok,
                    spf_aligned=spf_ok,
                    header_from=domain,
                    envelope_from=envelope,
                    dkim=[{"domain": signer, "selector": "s1", "result": "pass" if signer else "none"}]
                    if signer
                    else [],
                    spf=[{"domain": envelope, "result": "pass" if spf_ok or envelope != domain else "fail"}],
                )
            )
        if records:
            out.append(
                ParsedReport(
                    reporter=org,
                    reporter_email=addr,
                    report_id=f"demo-{domain}-{day.isoformat()}-{org}",
                    date_begin=begin,
                    date_end=end,
                    domain=domain,
                    policy=policy,
                    records=records,
                )
            )
    return out


def seed_demo_dmarc(force: bool = False) -> None:
    yesterday = timezone.now().date() - timedelta(days=1)
    fresh = DmarcReport.objects.filter(source=DmarcReport.Source.DEMO, date_begin__date=yesterday).exists()
    if fresh and not force:
        return
    if not cache.add("dmarc:demo-seed", 1, timeout=120):
        return
    try:
        with transaction.atomic():
            DmarcReport.objects.filter(source=DmarcReport.Source.DEMO).delete()
            now = timezone.now()
            for ip, (ptr, provider) in IPS.items():
                SourceIp.objects.update_or_create(
                    ip=ip, defaults={"ptr": ptr, "provider": provider, "looked_up_at": now}
                )
            for domain in PLAN:
                for i in range(DAYS, 0, -1):
                    day = yesterday - timedelta(days=i - 1)
                    rnd = random.Random(f"{domain}:{day.isoformat()}")  # noqa: S311 - deterministic sample data
                    for parsed in _reports_for(domain, day, rnd):
                        store_report(parsed, DmarcReport.Source.DEMO)
            # Make the newest reports look freshly received.
            DmarcReport.objects.filter(source=DmarcReport.Source.DEMO, date_begin__date=yesterday).update(
                received_at=now - timedelta(hours=3)
            )
    finally:
        cache.delete("dmarc:demo-seed")
