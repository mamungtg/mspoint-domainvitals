"""MX checks: existence, null MX (RFC 7505), resolvable hosts."""

from __future__ import annotations

import ipaddress

from ..resolver import BaseResolver, DnsLookupError
from .base import CRITICAL, INFO, WARNING, CheckResult


def check_mx(domain: str, resolver: BaseResolver) -> CheckResult:
    res = CheckResult("mx")
    try:
        mx = resolver.mx(domain)
        if mx is None:
            res.summary = "The domain does not exist in DNS."
            res.add(
                "domain_nxdomain",
                CRITICAL,
                "Domain does not exist",
                f"DNS returns NXDOMAIN for {domain}.",
                "Check the spelling and that the domain is registered and delegated.",
            )
            return res
        if not mx:
            res.summary = "No MX records; the domain cannot reliably receive mail."
            res.add(
                "mx_missing",
                WARNING,
                "No MX records",
                "Senders fall back to the domain's A record, which usually does not accept mail.",
                "Publish the MX records from your mail provider, or a null MX (0 .) if the domain never receives mail.",
            )
            res.data["hosts"] = []
            return res
        if len(mx) == 1 and mx[0][1] in ("", "."):
            res.summary = "Null MX: the domain declares that it does not receive mail."
            res.data.update(hosts=[], null_mx=True)
            res.add(
                "mx_null",
                INFO,
                "Null MX published",
                "This domain intentionally accepts no mail.",
                "Keep SPF at v=spf1 -all and DMARC at p=reject for non-mail domains.",
            )
            return res
        hosts = []
        for pref, host in mx:
            try:
                ipaddress.ip_address(host)
                is_ip = True
            except ValueError:
                is_ip = False
            addrs = [] if is_ip else resolver.addresses(host)
            hosts.append({"preference": pref, "host": host, "addresses": addrs[:4], "resolves": bool(addrs)})
            if is_ip:
                res.add(
                    "mx_is_ip",
                    CRITICAL,
                    "MX points to an IP address",
                    f"{host} is an IP address; MX records must name a host.",
                    "Use the mail server's hostname.",
                )
            elif not addrs:
                res.add(
                    "mx_unresolvable",
                    CRITICAL,
                    f"{host} does not resolve",
                    f"The MX host {host} has no A or AAAA record, so mail to it cannot be delivered.",
                    "Fix the host's DNS or remove the MX record.",
                )
        res.data["hosts"] = hosts
        res.record = ", ".join(f"{h['preference']} {h['host']}" for h in hosts)
        res.summary = (
            f"{len(hosts)} mail server{'s' if len(hosts) > 1 else ''} published and resolving."
            if res.status == "pass"
            else "Some mail servers have problems."
        )
    except DnsLookupError as exc:
        res.error = True
        res.summary = "DNS lookup timed out; the check will run again on the next scan."
        res.data["error"] = str(exc)
    return res
