"""Collect everything a PDF report shows, as plain data (easy to test)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.alerts.models import Alert
from apps.dmarc.reports import summarize as dmarc_summary
from apps.dns_monitor.checks import CHECK_ORDER
from apps.dns_monitor.models import DnsChange, DnsScan
from apps.ssl_monitor.reports import certificate_rows

MAX_DOMAINS = 100
SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def _findings(scan) -> list[dict]:
    out = []
    for check in CHECK_ORDER:
        for f in ((scan.results or {}).get(check) or {}).get("findings", []):
            if f.get("severity") in ("critical", "warning"):
                out.append({"check": check, **{k: f.get(k, "") for k in ("severity", "title", "fix")}})
    return sorted(out, key=lambda f: SEVERITY_RANK[f["severity"]])


def _trend(domain, since) -> list[tuple]:
    """One score per day (the last scan of each day)."""
    by_day = {}
    for created, score in (
        DnsScan.objects.filter(domain=domain, status="completed", created_at__gte=since, health_score__isnull=False)
        .order_by("created_at")
        .values_list("created_at", "health_score")
    ):
        by_day[created.date()] = score
    return sorted(by_day.items())


def build(org, domain_ids=None, days: int = 30) -> dict:
    now = timezone.now()
    since = now - timedelta(days=days)
    qs = org.domains.filter(verified_at__isnull=False).select_related("latest_scan").order_by("name")
    if domain_ids:
        qs = qs.filter(pk__in=domain_ids)
    domains = list(qs[:MAX_DOMAINS])

    certs_by_domain: dict = {}
    for row in certificate_rows(org.pk):
        certs_by_domain.setdefault(row["domain_id"], []).append(row)

    items = []
    for d in domains:
        scan = d.latest_scan
        dm = dmarc_summary([d.name], days)
        changes = list(
            DnsChange.objects.filter(domain=d, detected_at__gte=since)
            .order_by("-detected_at")
            .values("name", "rtype", "kind", "old_values", "new_values", "detected_at")[:10]
        )
        alerts = list(
            Alert.objects.filter(domain=d, status=Alert.Status.OPEN)
            .order_by("-opened_at")
            .values("severity", "title", "opened_at")[:10]
        )
        items.append(
            {
                "id": str(d.pk),
                "name": d.name,
                "score": scan.health_score if scan else None,
                "overall": scan.overall_status if scan else "",
                "checked_at": scan.completed_at if scan else None,
                "checks": {c: ((scan.summary or {}).get(c) if scan else None) for c in CHECK_ORDER},
                "findings": _findings(scan)[:8] if scan else [],
                "trend": _trend(d, since),
                "certificates": [
                    {k: c.get(k) for k in ("hostname", "port", "status", "days_left", "issuer", "not_after", "error")}
                    for c in certs_by_domain.get(str(d.pk), [])
                ],
                "dmarc": {
                    "messages": dm["totals"]["messages"],
                    "pass_rate": dm["totals"]["pass_rate"],
                    "senders": [
                        {k: s[k] for k in ("name", "messages", "pass_rate", "verdict")} for s in dm["senders"][:5]
                    ],
                },
                "dns_changes": changes,
                "alerts": alerts,
            }
        )

    scores = [i["score"] for i in items if i["score"] is not None]
    return {
        "organization": org.name,
        "generated_at": now,
        "since": since,
        "until": now,
        "days": days,
        "single": bool(domain_ids) and len(items) == 1,
        "domains": items,
        "totals": {
            "domains": len(items),
            "average_score": round(sum(scores) / len(scores)) if scores else None,
            "failing": sum(1 for i in items if i["overall"] == "fail"),
            "warnings": sum(1 for i in items if i["overall"] == "warn"),
            "healthy": sum(1 for i in items if i["overall"] == "pass"),
            "certs_expiring": sum(
                1 for i in items for c in i["certificates"] if c["days_left"] is not None and c["days_left"] <= 30
            ),
            "open_alerts": sum(len(i["alerts"]) for i in items),
        },
    }
