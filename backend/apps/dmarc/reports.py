"""Turn stored DMARC rows into the numbers the dashboard shows."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db.models import Case, IntegerField, Max, Sum, When
from django.utils import timezone

from .models import DmarcRecord, DmarcReport, SourceIp
from .sources import label, provider_for

RECEIVING_WITHIN = timedelta(days=4)
MAX_IPS = 500


def _passed_sum():
    return Sum(
        Case(
            When(dkim_aligned=True, then="count"),
            When(spf_aligned=True, then="count"),
            default=0,
            output_field=IntegerField(),
        )
    )


def _flag_sum(field):
    return Sum(Case(When(**{field: True}, then="count"), default=0, output_field=IntegerField()))


def rua_address() -> str:
    return settings.DMARC_RUA_ADDRESS


def _dmarc_result(domain) -> dict:
    scan = domain.latest_scan
    return (scan.results or {}).get("dmarc", {}) if scan else {}


def suggested_record(domain) -> str:
    """The domain's DMARC record with our reporting address added to rua=."""
    ours = f"mailto:{rua_address()}"
    res = _dmarc_result(domain)
    current = res.get("record") or ""
    if not current:
        return f"v=DMARC1; p=none; rua={ours}"
    parts = [p.strip() for p in current.split(";") if p.strip()]
    for i, p in enumerate(parts):
        if p.lower().startswith("rua="):
            addrs = [a.strip() for a in p[4:].split(",") if a.strip()]
            if ours.lower() not in (a.lower() for a in addrs):
                addrs.append(ours)
            parts[i] = "rua=" + ",".join(addrs)
            break
    else:
        parts.append(f"rua={ours}")
    return "; ".join(parts)


def reporting_status(domain, last_report) -> str:
    """receiving | waiting | not_configured | no_dmarc | unknown"""
    if last_report and timezone.now() - last_report <= RECEIVING_WITHIN:
        return "receiving"
    res = _dmarc_result(domain)
    if not res:
        return "unknown"
    if not res.get("record"):
        return "no_dmarc"
    rua = [a.lower() for a in (res.get("data") or {}).get("rua") or []]
    if f"mailto:{rua_address()}".lower() in rua or any(rua_address().lower() in a for a in rua):
        return "waiting"
    return "not_configured"


def domain_rows(domains, since) -> list[dict]:
    names = [d.name for d in domains]
    stats = {
        r["domain_name"]: r
        for r in DmarcRecord.objects.filter(domain_name__in=names, day__gte=since)
        .values("domain_name")
        .annotate(messages=Sum("count"), passed=_passed_sum())
    }
    last = dict(
        DmarcReport.objects.filter(domain_name__in=names)
        .values("domain_name")
        .annotate(last=Max("received_at"))
        .values_list("domain_name", "last")
    )
    rows = []
    for d in domains:
        st = stats.get(d.name) or {}
        messages = st.get("messages") or 0
        passed = st.get("passed") or 0
        res = _dmarc_result(d)
        rows.append(
            {
                "id": str(d.id),
                "name": d.name,
                "messages": messages,
                "passed": passed,
                "pass_rate": round(passed / messages, 4) if messages else None,
                "last_report": last[d.name].isoformat() if last.get(d.name) else None,
                "status": reporting_status(d, last.get(d.name)),
                "policy": (res.get("data") or {}).get("policy"),
                "suggested_record": suggested_record(d),
            }
        )
    return rows


def _verdict(messages, passed, provider) -> str:
    rate = passed / messages if messages else 0
    if rate >= 0.95:
        return "pass"
    if passed == 0 and not provider:
        return "fail"
    return "warn"


def summarize(domain_names: list[str], days: int = 30) -> dict:
    today = timezone.now().date()
    since = today - timedelta(days=days - 1)
    qs = DmarcRecord.objects.filter(domain_name__in=domain_names, day__gte=since)

    agg = qs.aggregate(
        messages=Sum("count"),
        passed=_passed_sum(),
        quarantined=Sum(Case(When(disposition="quarantine", then="count"), default=0, output_field=IntegerField())),
        rejected=Sum(Case(When(disposition="reject", then="count"), default=0, output_field=IntegerField())),
    )
    messages = agg["messages"] or 0
    passed = agg["passed"] or 0

    daily = {r["day"]: r for r in qs.values("day").annotate(messages=Sum("count"), passed=_passed_sum())}
    by_day = []
    for i in range(days):
        d = since + timedelta(days=i)
        r = daily.get(d) or {}
        by_day.append(
            {
                "day": d.isoformat(),
                "passed": r.get("passed") or 0,
                "failed": (r.get("messages") or 0) - (r.get("passed") or 0),
            }
        )

    per_ip = list(
        qs.values("source_ip")
        .annotate(
            messages=Sum("count"), passed=_passed_sum(), spf=_flag_sum("spf_aligned"), dkim=_flag_sum("dkim_aligned")
        )
        .order_by("-messages")[:MAX_IPS]
    )
    ips = [r["source_ip"] for r in per_ip]
    info = {s.ip: s for s in SourceIp.objects.filter(ip__in=ips)}
    # DKIM signing domains and From domains per IP give context and a fallback label.
    extra = defaultdict(lambda: {"dkim": set(), "from": set()})
    for ip, dkim, hf in qs.filter(source_ip__in=ips).values_list("source_ip", "dkim", "header_from")[:20000]:
        e = extra[ip]
        for d in dkim or []:
            if d.get("domain"):
                e["dkim"].add(d["domain"])
        if hf:
            e["from"].add(hf)

    senders: dict[str, dict] = {}
    for r in per_ip:
        ip = r["source_ip"]
        si = info.get(ip)
        ptr = si.ptr if si else ""
        provider = si.provider if si else ""
        dkim_domains = sorted(extra[ip]["dkim"])
        name = label(ip, ptr, provider, dkim_domains)
        known = provider or next((provider_for(d) for d in dkim_domains if provider_for(d)), "")
        s = senders.setdefault(
            name,
            {
                "name": name,
                "known": bool(known),
                "messages": 0,
                "passed": 0,
                "spf_aligned": 0,
                "dkim_aligned": 0,
                "ips": [],
            },
        )
        s["messages"] += r["messages"]
        s["passed"] += r["passed"]
        s["spf_aligned"] += r["spf"]
        s["dkim_aligned"] += r["dkim"]
        s["ips"].append(
            {
                "ip": ip,
                "ptr": ptr,
                "messages": r["messages"],
                "passed": r["passed"],
                "spf_aligned": r["spf"],
                "dkim_aligned": r["dkim"],
                "dkim_domains": dkim_domains[:5],
                "header_from": sorted(extra[ip]["from"])[:5],
            }
        )
    out = sorted(senders.values(), key=lambda s: -s["messages"])
    for s in out:
        s["verdict"] = _verdict(s["messages"], s["passed"], s["known"])
        s["pass_rate"] = round(s["passed"] / s["messages"], 4) if s["messages"] else None

    return {
        "days": days,
        "since": since.isoformat(),
        "totals": {
            "messages": messages,
            "passed": passed,
            "failed": messages - passed,
            "pass_rate": round(passed / messages, 4) if messages else None,
            "quarantined": agg["quarantined"] or 0,
            "rejected": agg["rejected"] or 0,
            "senders": len(out),
            "unauthenticated_senders": sum(1 for s in out if s["verdict"] == "fail"),
        },
        "by_day": by_day,
        "senders": out,
    }


def recent_reports(domain_name: str, limit: int = 12) -> list[dict]:
    return [
        {
            "id": str(r.id),
            "reporter": r.reporter,
            "date_begin": r.date_begin.isoformat(),
            "date_end": r.date_end.isoformat(),
            "messages": r.message_count,
            "policy": r.policy,
            "source": r.source,
            "received_at": r.received_at.isoformat(),
        }
        for r in DmarcReport.objects.filter(domain_name=domain_name).order_by("-date_begin")[:limit]
    ]
