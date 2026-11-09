"""DNS propagation: ask the domain's own name servers and several public
resolvers for the same record and compare. Authoritative answers are the
source of truth; public resolvers that differ are still serving cached data."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .resolver import BaseResolver, DnsLookupError, LiveResolver, rdata_text

PUBLIC_RESOLVERS = [
    ("Cloudflare", "1.1.1.1"),
    ("Google", "8.8.8.8"),
    ("Quad9", "9.9.9.9"),
    ("OpenDNS", "208.67.222.222"),
]
RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA"]


def find_zone(name: str, resolver: BaseResolver) -> str:
    labels = name.split(".")
    for i in range(0, max(1, len(labels) - 1)):
        candidate = ".".join(labels[i:])
        ns = resolver.records(candidate, "NS")
        if ns and ns["values"]:
            return candidate
    return ".".join(labels[-2:])


def _ask_authoritative(ip: str, name: str, rtype: str, timeout: float = 2.5) -> dict:
    import dns.exception
    import dns.flags
    import dns.message
    import dns.query
    import dns.rcode
    import dns.rdatatype

    q = dns.message.make_query(name, rtype)
    q.flags &= ~dns.flags.RD
    try:
        resp = dns.query.udp(q, ip, timeout=timeout)
        if resp.flags & dns.flags.TC:
            resp = dns.query.tcp(q, ip, timeout=timeout)
    except (dns.exception.DNSException, OSError) as exc:
        return {"error": f"No answer ({exc.__class__.__name__})"}
    if resp.rcode() == dns.rcode.NXDOMAIN:
        return {"values": [], "ttl": None, "nxdomain": True}
    want = dns.rdatatype.from_text(rtype)
    for rr in resp.answer:
        if rr.rdtype == want:
            return {"values": sorted(rdata_text(r, rtype) for r in rr), "ttl": rr.ttl}
    return {"values": [], "ttl": None}


def _ask_public(ip: str, name: str, rtype: str) -> dict:
    try:
        rs = LiveResolver(nameservers=[ip], timeout=2.5, lifetime=4).records(name, rtype)
    except DnsLookupError as exc:
        return {"error": str(exc)}
    if rs is None:
        return {"values": [], "ttl": None, "nxdomain": True}
    return rs


def check_propagation(name: str, rtype: str, *, resolver: BaseResolver | None = None, live: bool = True) -> dict:
    resolver = resolver or LiveResolver()
    zone = find_zone(name, resolver)
    auth = resolver.authoritative(zone)
    jobs = []
    for a in auth:
        if a.get("ip"):
            jobs.append(("authoritative", a["ns"], a["ip"]))
    for label, ip in PUBLIC_RESOLVERS:
        jobs.append(("public", label, ip))

    def run(job):
        kind, label, ip = job
        if not live:  # demo / tests: every server returns what the resolver has
            rs = resolver.records(name, rtype)
            ans = {"values": rs["values"] if rs else [], "ttl": rs["ttl"] if rs else None}
        else:
            ans = _ask_authoritative(ip, name, rtype) if kind == "authoritative" else _ask_public(ip, name, rtype)
        return {"kind": kind, "server": label, "ip": ip, **ans}

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, jobs))

    auth_sets = [tuple(r["values"]) for r in results if r["kind"] == "authoritative" and "error" not in r]
    expected = list(Counter(auth_sets).most_common(1)[0][0]) if auth_sets else None
    if expected is None:  # no authoritative answer: fall back to the majority of public resolvers
        pub = [tuple(r["values"]) for r in results if "error" not in r]
        expected = list(Counter(pub).most_common(1)[0][0]) if pub else []
    for r in results:
        if "error" in r:
            r["status"] = "error"
        elif sorted(r["values"]) == sorted(expected):
            r["status"] = "match"
        elif not r["values"]:
            r["status"] = "missing"
        else:
            r["status"] = "different"
    answered = [r for r in results if r["status"] != "error"]
    matched = sum(1 for r in answered if r["status"] == "match")
    return {
        "name": name,
        "type": rtype,
        "zone": zone,
        "expected": expected,
        "servers": results,
        "matched": matched,
        "answered": len(answered),
        "total": len(results),
        "propagated": bool(answered) and matched == len(answered),
    }
