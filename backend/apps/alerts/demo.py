"""Sample alerts for the demo workspace (no notifications are sent)."""

from datetime import timedelta

from django.utils import timezone

from .models import Alert

SAMPLES = [
    # domain, kind, key suffix, severity, status, title, detail, age in hours, resolved after hours
    (
        "brightpath-law.example",
        "check",
        "spf",
        "critical",
        "open",
        "SPF failing on brightpath-law.example",
        "• More than one SPF record — Merge them into a single TXT record that starts with v=spf1.",
        330,
        None,
    ),
    (
        "brightpath-law.example",
        "check",
        "dmarc",
        "critical",
        "open",
        "DMARC failing on brightpath-law.example",
        "• No DMARC record — Publish a TXT record at _dmarc.brightpath-law.example.",
        330,
        None,
    ),
    (
        "atlas-fitness.example",
        "check",
        "dns",
        "critical",
        "open",
        "DNS failing on atlas-fitness.example",
        "• www points to a name that no longer exists — Remove the CNAME or point it at a live host; "
        "a dangling CNAME can be taken over.",
        160,
        None,
    ),
    (
        "greenleaf-accounting.example",
        "certificate",
        "apex",
        "critical",
        "open",
        "Certificate on greenleaf-accounting.example has expired",
        "• Certificate expired — Renew it now; visitors see a security warning. Check why automatic renewal stopped.",
        72,
        None,
    ),
    (
        "atlas-fitness.example",
        "certificate",
        "apex",
        "critical",
        "open",
        "Certificate on atlas-fitness.example expires in 5 days",
        "• Certificate expires in 5 days — Renew it or confirm that automatic renewal is working.",
        50,
        None,
    ),
    (
        "harbour-dental.example",
        "check",
        "dmarc",
        "warning",
        "open",
        "DMARC needs attention on harbour-dental.example",
        "• Policy is p=none (monitoring only) — After reviewing reports, move to p=quarantine and then p=reject.",
        330,
        None,
    ),
    (
        "northwind-logistics.example",
        "dmarc_sender",
        "dmarc",
        "warning",
        "notice",
        "2 new unauthenticated senders for northwind-logistics.example",
        "These servers sent mail as this domain and failed SPF and DKIM.\n• 203.0.113.201: 31 messages\n• 203.0.113.202: 12 messages",
        20,
        None,
    ),
    (
        "harbour-dental.example",
        "dns_change",
        "dns",
        "info",
        "notice",
        "1 DNS record change on harbour-dental.example",
        "• harbour-dental.example A changed: 203.0.113.80",
        168,
        None,
    ),
    (
        "northwind-logistics.example",
        "check",
        "dmarc",
        "warning",
        "resolved",
        "DMARC needs attention on northwind-logistics.example",
        "• Policy applies to 50% of mail — Raise pct to 100.",
        400,
        168,
    ),
]


def seed_demo_alerts(org) -> None:
    """Re-created once a day so ages and day counts stay believable."""
    now = timezone.now()
    today = now.date().isoformat()
    if Alert.objects.filter(organization=org, data__seeded=today).exists():
        return
    Alert.objects.filter(organization=org).delete()
    domains = {d.name: d for d in org.domains.all()}
    for name, kind, suffix, severity, status, title, detail, age, resolved_after in SAMPLES:
        d = domains.get(name)
        if d is None:
            continue
        a = Alert.objects.create(
            organization=org,
            domain=d,
            kind=kind,
            key=f"demo:{kind}:{suffix}:{d.pk}",
            severity=severity,
            status=status,
            title=title,
            detail=detail,
            data={"seeded": today},
        )
        opened = now - timedelta(hours=age)
        Alert.objects.filter(pk=a.pk).update(
            opened_at=opened,
            updated_at=opened + timedelta(hours=resolved_after) if resolved_after else opened,
            resolved_at=opened + timedelta(hours=resolved_after) if resolved_after else None,
        )
