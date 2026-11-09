"""Certificate summaries shared by the certificates page and the overview."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from .evaluate import days_left
from .models import MonitoredHost


def _month_starts(today: date, n: int = 12) -> list[date]:
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def certificate_rows(org_id):
    now = timezone.now()
    rows = []
    hosts = (
        MonitoredHost.objects.filter(domain__organization_id=org_id)
        .select_related("domain", "latest_scan")
        .order_by("domain__name", "hostname")
    )
    for h in hosts:
        sc = h.latest_scan
        cert = sc.certificate if sc else {}
        rows.append(
            {
                "id": str(h.id),
                "hostname": h.hostname,
                "port": h.port,
                "label": h.label,
                "enabled": h.enabled,
                "domain_id": str(h.domain_id),
                "domain": h.domain.name,
                "domain_verified": h.domain.is_verified,
                "status": sc.result_status if sc else None,
                "scanned_at": sc.completed_at.isoformat() if sc and sc.completed_at else None,
                "pending": bool(sc and sc.status == "queued"),
                "days_left": days_left(cert.get("not_after", ""), now) if cert else None,
                "not_after": cert.get("not_after") or None,
                "issuer": cert.get("issuer_org") or cert.get("issuer") or None,
                "tls_version": cert.get("tls_version") or None,
                "findings": sc.findings if sc else [],
                "error": sc.error if sc else "",
            }
        )
    return rows


def summarize(rows) -> dict:
    today = timezone.now().date()
    months = _month_starts(today)
    buckets = {m: 0 for m in months}
    s = {
        "total": len(rows),
        "checked": 0,
        "expired": 0,
        "within_7": 0,
        "within_30": 0,
        "failing": 0,
        "healthy": 0,
        "unreachable": 0,
    }
    for r in rows:
        if r["status"] is None:
            continue
        s["checked"] += 1
        d = r["days_left"]
        if r["status"] == "error":
            s["unreachable"] += 1
        elif r["status"] == "fail":
            s["failing"] += 1
        elif r["status"] == "pass":
            s["healthy"] += 1
        if d is not None:
            if d < 0:
                s["expired"] += 1
            elif d <= 7:
                s["within_7"] += 1
            elif d <= 30:
                s["within_30"] += 1
        if r["not_after"]:
            end = date.fromisoformat(r["not_after"][:10])
            key = date(end.year, end.month, 1)
            if key in buckets:
                buckets[key] += 1
    s["by_month"] = [{"month": m.isoformat()[:7], "count": c} for m, c in buckets.items()]
    return s
