"""DNS infrastructure: name servers, SOA, apex/www addressing, CNAME safety, TTLs.

Also builds the record inventory that change detection compares between scans.
"""

from __future__ import annotations

from ..resolver import BaseResolver, DnsLookupError, soa_serial
from .base import CRITICAL, INFO, WARNING, CheckResult

APEX_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CAA"]
HOST_TYPES = ["A", "AAAA", "CNAME"]
TTL_LOW, TTL_HIGH = 300, 86400

# RFC 1912 section 2.2 recommended SOA ranges (seconds)
SOA_RANGES = {"refresh": (1200, 43200), "retry": (120, 7200), "expire": (1209600, 2419200), "minimum": (300, 86400)}


def collect_records(domain: str, resolver: BaseResolver, *, hosts: list[str], dkim_selectors: list[str]) -> dict:
    """{"<name> <TYPE>": {"ttl": int, "values": [...]}} for every non-empty record set."""
    inv: dict[str, dict] = {}

    def grab(name, rtype):
        rs = resolver.records(name, rtype)
        if rs and rs["values"]:
            inv[f"{name} {rtype}"] = rs

    for t in APEX_TYPES:
        grab(domain, t)
    for h in hosts:
        cname = resolver.records(h, "CNAME")
        if cname and cname["values"]:
            inv[f"{h} CNAME"] = cname
            continue  # a CNAME name carries no other data
        for t in ("A", "AAAA"):
            grab(h, t)
    grab(f"_dmarc.{domain}", "TXT")
    for sel in dkim_selectors:
        grab(f"{sel}._domainkey.{domain}", "TXT")
    return inv


def check_infra(domain: str, resolver: BaseResolver, *, hosts: list[str], dkim_selectors: list[str]) -> CheckResult:
    res = CheckResult("dns")
    try:
        inv = collect_records(domain, resolver, hosts=hosts, dkim_selectors=dkim_selectors)
        ns = inv.get(f"{domain} NS", {}).get("values", [])
        soa = inv.get(f"{domain} SOA", {}).get("values", [])
        auth = resolver.authoritative(domain) if ns else []
        res.data = {"records": inv, "name_servers": auth, "hosts": hosts}

        # ---- Name servers --------------------------------------------------
        if not ns:
            res.add(
                "dns_ns_missing",
                CRITICAL,
                "No name servers found",
                "The domain has no NS records, so nothing can resolve it.",
                "Check the delegation at your registrar.",
            )
        elif len(ns) < 2:
            res.add(
                "dns_ns_single",
                WARNING,
                "Only one name server",
                "If that server is unreachable the whole domain stops resolving (RFC 1034 asks for at least two).",
                "Add a second name server on a different network.",
            )
        unreachable = [a for a in auth if a["error"] and not a["authoritative"]]
        for a in unreachable:
            lame = a["ip"] and "authority" in a["error"]
            res.add(
                "dns_ns_lame" if lame else "dns_ns_unreachable",
                WARNING,
                f"{a['ns']} is not answering for this domain" if lame else f"{a['ns']} did not respond",
                f"{a['error']}. Resolvers that pick this server get slow or failed answers.",
                "Remove the server from the delegation or configure the zone on it.",
            )
        serials = {a["serial"] for a in auth if a["authoritative"] and a["serial"] is not None}
        if len(serials) > 1:
            res.add(
                "dns_soa_serial_mismatch",
                WARNING,
                "Name servers serve different zone versions",
                f"SOA serials differ between servers ({', '.join(str(s) for s in sorted(serials))}). A change has not reached every server.",
                "Wait for zone transfer, or check that secondary servers can transfer the zone from the primary.",
            )

        # ---- SOA -------------------------------------------------------------
        if not soa and ns:
            res.add(
                "dns_soa_missing",
                CRITICAL,
                "No SOA record",
                "Every DNS zone needs an SOA record.",
                "Check the zone configuration at your DNS provider.",
            )
        elif soa:
            parts = soa[0].split()
            if len(parts) >= 7:
                vals = dict(zip(["refresh", "retry", "expire", "minimum"], map(int, parts[3:7]), strict=False))
                res.data["soa"] = {"primary": parts[0].rstrip("."), "serial": soa_serial(soa), **vals}
                odd = [f"{k} {v}s" for k, v in vals.items() if not SOA_RANGES[k][0] <= v <= SOA_RANGES[k][1]]
                if odd:
                    res.add(
                        "dns_soa_values",
                        INFO,
                        "SOA timers outside the usual range",
                        f"{', '.join(odd)}. These control how secondaries refresh and how long missing answers are cached.",
                        "Most managed DNS providers set these for you; only change them if you run your own servers.",
                    )

        # ---- Apex and hosts --------------------------------------------------
        if f"{domain} A" not in inv and f"{domain} AAAA" not in inv:
            res.add(
                "dns_apex_no_address",
                INFO,
                f"{domain} has no A or AAAA record",
                "Visitors who type the bare domain cannot reach a website.",
                "Add an A record (or your provider's ALIAS/flattened CNAME) if the domain should serve a site.",
            )
        if resolver.records(domain, "CNAME") and resolver.records(domain, "CNAME")["values"]:
            res.add(
                "dns_cname_apex",
                CRITICAL,
                "CNAME at the zone apex",
                "A CNAME on the bare domain conflicts with its NS, SOA and MX records and breaks mail and delegation.",
                "Replace it with A/AAAA records or an ALIAS/flattened record.",
            )
        for h in hosts:
            cname = inv.get(f"{h} CNAME")
            if not cname:
                continue
            target = cname["values"][0].rstrip(".")
            if resolver.records(target, "A") is None and resolver.records(target, "AAAA") is None:
                res.add(
                    "dns_dangling_cname",
                    CRITICAL,
                    f"{h} points to a name that does not exist",
                    f"{h} is a CNAME to {target}, which returns NXDOMAIN. If that name can be claimed on a hosting "
                    "service, someone else could serve content on your subdomain (subdomain takeover).",
                    f"Remove the CNAME on {h}, or recreate the resource it points to.",
                )

        # ---- TTLs ------------------------------------------------------------
        low = [
            k for k, v in inv.items() if k.split()[1] in ("NS", "MX") and v["ttl"] is not None and v["ttl"] < TTL_LOW
        ]
        high = [
            k
            for k, v in inv.items()
            if k.split()[1] in ("A", "AAAA", "CNAME", "MX") and v["ttl"] and v["ttl"] > TTL_HIGH
        ]
        if low:
            res.add(
                "dns_ttl_low",
                INFO,
                "Very short TTL on core records",
                f"{', '.join(low)} use a TTL under {TTL_LOW} seconds, which increases query load and slows lookups when your DNS provider is slow.",
                "Use 3600 seconds or more unless you are about to change these records.",
            )
        if high:
            res.add(
                "dns_ttl_high",
                INFO,
                "Very long TTL",
                f"{', '.join(high)} are cached for more than a day, so changes take a long time to reach everyone.",
                "Lower the TTL a day before a planned change.",
            )

        n = len(inv)
        res.summary = {
            "pass": f"{len(ns)} name servers and {n} record sets look healthy.",
            "warn": "DNS works but has issues worth fixing.",
            "fail": "DNS has problems that can break the domain.",
        }.get(res.status, "")
    except DnsLookupError as exc:
        res.error = True
        res.summary = "DNS lookup timed out; the check will run again on the next scan."
        res.data["error"] = str(exc)
    return res
