"""Read-only sample workspace.

Sample domains use the reserved .example TLD (RFC 2606) so no real business
is shown with a broken configuration. Results are produced by running the real
check engine against an in-memory DNS zone; nothing here is hard-coded output.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.dns_monitor.models import DnsScan
from apps.dns_monitor.resolver import FakeResolver
from apps.dns_monitor.services import execute_scan
from apps.organizations.models import Membership, Organization, Role

from .models import Domain

DEMO_NAME = "Demo workspace (sample data)"
HISTORY_DAYS = 14
CHANGE_DAY = 7  # days ago when two sample domains changed configuration


def _key(seed: str, der_len: int) -> str:
    """Deterministic base64 blob with the length of a real RSA public key."""
    raw = b""
    while len(raw) < der_len:
        raw += hashlib.sha256((seed + str(len(raw))).encode()).digest()
    return base64.b64encode(raw[:der_len]).decode()


KEY_2048 = lambda s: f"v=DKIM1; k=rsa; p={_key(s, 294)}"  # noqa: E731
KEY_1024 = lambda s: f"v=DKIM1; k=rsa; p={_key(s, 162)}"  # noqa: E731


def build_zone(after_change: bool) -> dict:
    z: dict[str, dict] = {}

    def add(name, **types):
        z.setdefault(name, {}).update(types)

    # Shared "provider" infrastructure ---------------------------------------
    add("_spf.mailhost.example", TXT=["v=spf1 include:_netblocks.mailhost.example ~all"])
    add("_netblocks.mailhost.example", TXT=["v=spf1 ip4:192.0.2.0/24 ip4:198.51.100.0/24 ~all"])
    add("spf.protection.outlook.example", TXT=["v=spf1 ip4:203.0.113.0/24 -all"])
    for h in ("aspmx.mailhost.example", "alt1.aspmx.mailhost.example", "mx1.outlook.example"):
        add(h, A=["192.0.2.25"])

    # 1. Harbour Dental: fine except DMARC monitoring only ---------------------
    d = "harbour-dental.example"
    add(
        d,
        TXT=["v=spf1 include:_spf.mailhost.example ~all"],
        MX=[(1, "aspmx.mailhost.example"), (5, "alt1.aspmx.mailhost.example")],
    )
    add(f"google._domainkey.{d}", TXT=[KEY_2048(d)])
    add(f"_dmarc.{d}", TXT=[f"v=DMARC1; p=none; rua=mailto:dmarc@{d}"])

    # 2. Northwind Logistics: moved from quarantine 50% to reject ---------------
    d = "northwind-logistics.example"
    add(d, TXT=["v=spf1 include:spf.protection.outlook.example -all"], MX=[(0, "mx1.outlook.example")])
    add(f"selector1._domainkey.{d}", TXT=[KEY_2048(d + "1")])
    add(f"selector2._domainkey.{d}", TXT=[KEY_2048(d + "2")])
    add(
        f"_dmarc.{d}",
        TXT=[
            f"v=DMARC1; p=reject; rua=mailto:dmarc-reports@{d}"
            if after_change
            else f"v=DMARC1; p=quarantine; pct=50; rua=mailto:dmarc-reports@{d}"
        ],
    )

    # 3. Brightpath Law: two SPF records, no DMARC -------------------------------
    d = "brightpath-law.example"
    add(
        d,
        TXT=["v=spf1 include:_spf.mailhost.example ~all", "v=spf1 ip4:203.0.113.10 -all"],
        MX=[(1, "aspmx.mailhost.example")],
    )
    add(f"google._domainkey.{d}", TXT=[KEY_2048(d)])

    # 4. Greenleaf Accounting: a new sending service pushed SPF over 10 lookups --
    d = "greenleaf-accounting.example"
    services = ["crm", "billing", "newsletter", "helpdesk", "payroll"] + (["surveys"] if after_change else [])
    for svc in services:
        add(f"spf.{svc}.example", TXT=[f"v=spf1 include:net.{svc}.example ~all"])
        add(f"net.{svc}.example", TXT=["v=spf1 ip4:198.51.100.0/26 ~all"])
    add(
        d,
        TXT=["v=spf1 " + " ".join(f"include:spf.{s}.example" for s in services) + " -all"],
        MX=[(10, "mx1.outlook.example")],
    )
    add(f"k1._domainkey.{d}", TXT=[KEY_1024(d)])
    add(f"_dmarc.{d}", TXT=[f"v=DMARC1; p=quarantine; pct=50; rua=mailto:dmarc@{d}"])

    # 5. Atlas Fitness: +all and a dead backup MX ---------------------------------
    d = "atlas-fitness.example"
    add(d, TXT=["v=spf1 +all"], MX=[(10, f"mail.{d}"), (20, f"backup.{d}")])
    add(f"mail.{d}", A=["198.51.100.40"])
    add(f"backup.{d}", TXT=[])  # exists but has no A record
    add(f"_dmarc.{d}", TXT=[f"v=DMARC1; p=reject; rua=mailto:postmaster@{d}"])

    # 6. Coastal Realty: added but not yet verified (no zone needed) -------------

    # DNS infrastructure for every verified sample domain ----------------------
    serial = 2026110101 if not after_change else 2026110209
    infra = {
        "harbour-dental.example": dict(ns=2, www="cname"),
        "northwind-logistics.example": dict(ns=3, www="a"),
        "brightpath-law.example": dict(ns=2, www="a", serial_split=True),
        "greenleaf-accounting.example": dict(ns=2, www="none", apex_a=False, mx_ttl=60),
        "atlas-fitness.example": dict(ns=1, www="dangling"),
    }
    for d, cfg in infra.items():
        ns = [f"ns{i}.dnshost.example" for i in range(1, cfg["ns"] + 1)]
        apex_ip = "203.0.113.20" if (d != "harbour-dental.example" or not after_change) else "203.0.113.80"
        add(
            d,
            NS=ns,
            SOA=[f"ns1.dnshost.example. hostmaster.{d}. {serial} 7200 3600 1209600 3600"],
            TTL={"NS": 86400, "SOA": 3600, "MX": cfg.get("mx_ttl", 3600), "A": 3600, "TXT": 3600},
        )
        if cfg.get("apex_a", True):
            add(d, A=[apex_ip])
        if cfg["www"] == "cname":
            add(f"www.{d}", CNAME=[d], A=[apex_ip])
        elif cfg["www"] == "a":
            add(f"www.{d}", A=["203.0.113.21"])
        elif cfg["www"] == "dangling":
            add(f"www.{d}", CNAME=["atlas-fitness.oldsitehost.example"])
        if cfg.get("serial_split"):
            z[d]["AUTH"] = [
                {"ns": "ns1.dnshost.example", "ip": "192.0.2.53", "authoritative": True, "serial": serial, "error": ""},
                {
                    "ns": "ns2.dnshost.example",
                    "ip": "192.0.2.54",
                    "authoritative": True,
                    "serial": serial - 8,
                    "error": "",
                },
            ]
    for i in range(1, 4):
        add(f"ns{i}.dnshost.example", A=[f"192.0.2.{52 + i}"])
    return z


SAMPLE_DOMAINS = [
    ("harbour-dental.example", True, ["google"]),
    ("northwind-logistics.example", True, []),
    ("brightpath-law.example", True, []),
    ("greenleaf-accounting.example", True, []),
    ("atlas-fitness.example", True, []),
    ("coastal-realty.example", False, []),
]


def demo_resolver(after_change: bool = True) -> FakeResolver:
    return FakeResolver(build_zone(after_change))


@transaction.atomic
def ensure_demo_workspace(user) -> Organization:
    from apps.ssl_monitor.demo import seed_demo_tls

    existing = Organization.objects.filter(is_demo=True, memberships__user=user).first()
    if existing:
        # Workspaces created before record tracking existed get fresh history.
        if DnsScan.objects.filter(domain__organization=existing, status=DnsScan.Status.COMPLETED, records={}).exists():
            DnsScan.objects.filter(domain__organization=existing).delete()
            _seed_history(existing)
        seed_demo_tls(existing)
        return existing
    org = Organization.objects.create(name=DEMO_NAME, owner=user, is_demo=True, timezone="UTC")
    # Viewer role: the sample is read-only and can be left at any time.
    Membership.objects.create(organization=org, user=user, role=Role.VIEWER)
    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    for name, verified, selectors in SAMPLE_DOMAINS:
        Domain.objects.create(
            organization=org,
            name=name,
            dkim_selectors=selectors,
            verified_at=now - timedelta(days=HISTORY_DAYS + 1) if verified else None,
            verification_checked_at=now if verified else None,
        )
    _seed_history(org)
    seed_demo_tls(org, force=True)
    return org


def _seed_history(org) -> None:
    """14 daily scans per verified sample domain; configuration changes CHANGE_DAY
    days ago so the history, trend and change log have something to show."""
    before, after = demo_resolver(False), demo_resolver(True)
    for dom in org.domains.filter(verified_at__isnull=False):
        for days_ago in range(HISTORY_DAYS - 1, -1, -1):
            when = timezone.now() - timedelta(days=days_ago)  # same clock time each day: one scan per calendar day
            scan = DnsScan.objects.create(domain=dom, trigger=DnsScan.Trigger.DEMO, created_at=when)
            execute_scan(scan, after if days_ago < CHANGE_DAY else before, when=when)
