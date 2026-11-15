"""Turn scan results into alerts.

Problems (failing checks, certificates) open once, escalate if they get worse
and resolve when fixed, so a problem that stays broken does not notify again
on every scan. DNS changes and new DMARC senders are one-off notices.
"""

from __future__ import annotations

from collections import defaultdict

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.dns_monitor.checks import CHECK_ORDER

from .models import SEVERITY_RANK, Alert, Kind, Severity
from .notify import dispatch

CHECK_NAMES = {"spf": "SPF", "dkim": "DKIM", "dmarc": "DMARC", "mx": "MX", "dns": "DNS"}


def sync(org, domain, kind, key, severity, title, detail="", data=None) -> Alert | None:
    """Open, update, escalate or (with severity=None) resolve the alert for ``key``."""
    current = Alert.objects.filter(organization=org, key=key, status=Alert.Status.OPEN).first()
    if severity is None:
        if current:
            current.status, current.resolved_at = Alert.Status.RESOLVED, timezone.now()
            current.save(update_fields=["status", "resolved_at", "updated_at"])
            dispatch(current, "resolved")
        return current
    if current:
        escalated = SEVERITY_RANK[severity] > SEVERITY_RANK[current.severity]
        changed = (current.severity, current.title, current.detail) != (severity, title, detail)
        if changed:
            current.severity, current.title, current.detail, current.data = severity, title, detail, data or {}
            if escalated:  # someone acknowledged the warning, not the critical
                current.acknowledged_by, current.acknowledged_at = None, None
            current.save()
        if escalated:
            dispatch(current, "escalated")
        return current
    try:
        with transaction.atomic():
            alert = Alert.objects.create(
                organization=org,
                domain=domain,
                kind=kind,
                key=key,
                severity=severity,
                title=title,
                detail=detail,
                data=data or {},
            )
    except IntegrityError:  # opened concurrently by another worker
        return Alert.objects.filter(organization=org, key=key, status=Alert.Status.OPEN).first()
    dispatch(alert, "opened")
    return alert


def notice(org, domain, kind, key, severity, title, detail="", data=None) -> Alert:
    alert = Alert.objects.create(
        organization=org,
        domain=domain,
        kind=kind,
        key=key,
        severity=severity,
        status=Alert.Status.NOTICE,
        title=title,
        detail=detail,
        data=data or {},
    )
    dispatch(alert, "notice")
    return alert


def _findings_text(result: dict, limit: int = 3) -> str:
    rank = {"critical": 0, "warning": 1, "info": 2}
    items = sorted(
        (f for f in result.get("findings", []) if f.get("severity") in ("critical", "warning")),
        key=lambda f: rank[f["severity"]],
    )
    lines = [f"• {f['title']}" + (f" — {f['fix']}" if f.get("fix") else "") for f in items[:limit]]
    if len(items) > limit:
        lines.append(f"• and {len(items) - limit} more")
    return "\n".join(lines)


def evaluate_scan(scan) -> None:
    domain = scan.domain
    org = domain.organization
    if org.is_demo or scan.status != "completed":
        return
    for check in CHECK_ORDER:
        res = (scan.results or {}).get(check)
        if not res or res.get("status") == "error":
            continue  # lookup trouble: keep whatever state we had
        status = res.get("status")
        severity = {"fail": Severity.CRITICAL, "warn": Severity.WARNING}.get(status)
        word = "failing" if status == "fail" else "needs attention"
        sync(
            org,
            domain,
            Kind.CHECK,
            f"check:{check}:{domain.pk}",
            severity,
            f"{CHECK_NAMES[check]} {word} on {domain.name}",
            _findings_text(res),
            {"check": check, "scan_id": str(scan.pk)},
        )

    changes = list(scan.changes.all())
    if changes:
        lines = []
        for c in changes[:10]:
            if c.kind == "ttl":
                lines.append(f"• {c.name} {c.rtype}: TTL {c.old_ttl} → {c.new_ttl}")
            else:
                lines.append(f"• {c.name} {c.rtype} {c.kind}: {', '.join(c.new_values or c.old_values)[:200]}")
        if len(changes) > 10:
            lines.append(f"• and {len(changes) - 10} more")
        notice(
            org,
            domain,
            Kind.DNS_CHANGE,
            f"dns:{scan.pk}",
            Severity.INFO,
            f"{len(changes)} DNS record change{'s' if len(changes) != 1 else ''} on {domain.name}",
            "\n".join(lines),
            {"scan_id": str(scan.pk), "count": len(changes)},
        )


def evaluate_tls(scan) -> None:
    from apps.ssl_monitor.evaluate import days_left

    host = scan.host
    domain = host.domain
    org = domain.organization
    if org.is_demo:
        return
    label = host.hostname if host.port == 443 else f"{host.hostname}:{host.port}"
    days = days_left((scan.certificate or {}).get("not_after", ""), timezone.now()) if scan.certificate else None
    findings = [f for f in (scan.findings or []) if f.get("severity") in ("critical", "warning")]
    detail = "\n".join(f"• {f['title']}" + (f" — {f['fix']}" if f.get("fix") else "") for f in findings[:3])

    if scan.result_status == "error":
        severity, title = Severity.WARNING, f"Cannot check the certificate on {label}"
    elif days is not None and days < 0:
        severity, title = Severity.CRITICAL, f"Certificate on {label} has expired"
    elif days is not None and days <= 7:
        severity, title = Severity.CRITICAL, f"Certificate on {label} expires in {days} day{'s' if days != 1 else ''}"
    elif scan.result_status == "fail":
        severity, title = Severity.CRITICAL, f"Certificate problem on {label}"
    elif days is not None and days <= 30:
        severity, title = Severity.WARNING, f"Certificate on {label} expires in {days} days"
    elif scan.result_status == "warn":
        severity, title = Severity.WARNING, f"Certificate on {label} needs attention"
    else:
        severity, title = None, f"Certificate on {label}"
    # The day count in the title changes daily; that updates the alert quietly
    # (only opening, escalation and resolution notify).
    sync(
        org,
        domain,
        Kind.CERTIFICATE,
        f"cert:{host.pk}",
        severity,
        title,
        detail,
        {"host_id": str(host.pk), "days_left": days},
    )


def evaluate_dmarc(report_ids) -> None:
    """One notice per domain when a report shows mail failing DMARC from an IP
    that has not sent for that domain in the previous 90 days."""
    from datetime import timedelta

    from django.db.models import Sum

    from apps.dmarc.models import DmarcRecord, DmarcReport
    from apps.domains.models import Domain

    reports = list(DmarcReport.objects.filter(pk__in=report_ids).exclude(source="demo"))
    by_domain = defaultdict(list)
    for r in reports:
        by_domain[r.domain_name].append(r)
    for name, reps in by_domain.items():
        earliest = min(r.date_begin for r in reps)
        failing = (
            DmarcRecord.objects.filter(report__in=reps, dkim_aligned=False, spf_aligned=False)
            .values("source_ip")
            .annotate(n=Sum("count"))
        )
        known = set(
            DmarcRecord.objects.filter(domain_name=name, day__gte=(earliest - timedelta(days=90)).date())
            .exclude(report__in=reps)
            .values_list("source_ip", flat=True)
        )
        new = sorted((f for f in failing if f["source_ip"] not in known), key=lambda f: -f["n"])
        if not new:
            continue
        total = sum(f["n"] for f in new)
        lines = [f"• {f['source_ip']}: {f['n']} message{'s' if f['n'] != 1 else ''}" for f in new[:10]]
        detail = (
            "These servers sent mail as this domain and failed SPF and DKIM. If you don't recognise them, "
            "someone may be spoofing the domain.\n" + "\n".join(lines)
        )
        for domain in Domain.objects.filter(
            name=name, verified_at__isnull=False, organization__is_demo=False
        ).select_related("organization"):
            notice(
                domain.organization,
                domain,
                Kind.DMARC_SENDER,
                f"dmarc:{name}:{reps[0].pk}",
                Severity.WARNING,
                f"{len(new)} new unauthenticated sender{'s' if len(new) != 1 else ''} for {name}",
                detail,
                {"ips": [f["source_ip"] for f in new[:50]], "messages": total},
            )
