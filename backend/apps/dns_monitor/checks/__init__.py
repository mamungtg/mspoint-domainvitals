"""Run all DNS checks for a domain and score the result."""

from __future__ import annotations

from ..resolver import BaseResolver, DnsLookupError
from .base import CRITICAL, ERROR, FAIL, PASS, WARN, WARNING, CheckResult
from .dkim import check_dkim
from .dmarc import check_dmarc
from .infra import check_infra
from .mx import check_mx
from .spf import check_spf

CHECK_ORDER = ["spf", "dkim", "dmarc", "mx", "dns"]
PENALTY = {CRITICAL: 25, WARNING: 10}


def run_checks(
    domain: str, resolver: BaseResolver, dkim_selectors: list[str] | None = None, hosts: list[str] | None = None
) -> dict:
    results: dict[str, CheckResult] = {
        "spf": check_spf(domain, resolver),
        "dkim": check_dkim(domain, resolver, dkim_selectors),
        "dmarc": check_dmarc(domain, resolver),
        "mx": check_mx(domain, resolver),
    }
    found = [k["selector"] for k in results["dkim"].data.get("selectors", [])]
    results["dns"] = check_infra(
        domain, resolver, hosts=hosts if hosts is not None else [f"www.{domain}"], dkim_selectors=found
    )
    findings = [f for r in results.values() for f in r.findings]
    critical = sum(1 for f in findings if f.severity == CRITICAL)
    warning = sum(1 for f in findings if f.severity == WARNING)
    score = max(0, 100 - critical * PENALTY[CRITICAL] - warning * PENALTY[WARNING])
    statuses = [r.status for r in results.values()]
    if FAIL in statuses:
        overall = FAIL
    elif WARN in statuses:
        overall = WARN
    elif ERROR in statuses:
        overall = ERROR
    else:
        overall = PASS
    return {
        "score": score,
        "overall": overall,
        "critical": critical,
        "warning": warning,
        "summary": {k: r.status for k, r in results.items()},
        "results": {k: r.to_dict() for k, r in results.items()},
    }


def verify_ownership(domain: str, token: str, resolver: BaseResolver) -> bool:
    """True when _domainvitals.<domain> has TXT 'domainvitals-verify=<token>'."""
    try:
        txts = resolver.txt(f"_domainvitals.{domain}") or []
    except DnsLookupError:
        return False
    expected = f"domainvitals-verify={token}"
    return any(t.strip() == expected for t in txts)


__all__ = [
    "run_checks",
    "verify_ownership",
    "CHECK_ORDER",
    "check_spf",
    "check_dkim",
    "check_dmarc",
    "check_mx",
    "check_infra",
]
