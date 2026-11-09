"""DNS access for the check engine.

Checks only ever *query public DNS* (TXT, MX, A/AAAA). They never open a
connection to a customer-supplied host, so there is no SSRF surface here.

`LiveResolver` talks to a fixed set of public recursive resolvers with strict
timeouts. `FakeResolver` serves an in-memory zone (tests, demo workspace).
"""

from __future__ import annotations

import dns.exception
import dns.name
import dns.rdatatype
import dns.resolver
from django.conf import settings


class DnsLookupError(Exception):
    """Transient failure (timeout, SERVFAIL, no reachable nameserver)."""


def _norm(name: str) -> str:
    return name.strip().rstrip(".").lower()


class BaseResolver:
    """Interface used by the checks.

    txt():       None if the name does not exist (NXDOMAIN), [] if it exists
                 with no TXT records, else the joined TXT strings.
    mx():        None on NXDOMAIN, else list of (preference, host).
    addresses(): A + AAAA addresses ([] if none).
    """

    queries = 0

    def txt(self, name: str) -> list[str] | None:  # pragma: no cover - interface
        raise NotImplementedError

    def mx(self, name: str) -> list[tuple[int, str]] | None:  # pragma: no cover
        raise NotImplementedError

    def addresses(self, name: str) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    def records(self, name: str, rtype: str) -> dict | None:  # pragma: no cover
        """{"ttl": int|None, "values": [sorted text values]}; None on NXDOMAIN."""
        raise NotImplementedError

    def authoritative(self, domain: str) -> list[dict]:  # pragma: no cover
        """One entry per name server: {"ns", "ip", "authoritative", "serial", "error"}."""
        raise NotImplementedError


class LiveResolver(BaseResolver):
    MAX_QUERIES = 140  # hard ceiling per scan (SPF recursion, DKIM selectors, record inventory...)

    def __init__(self, nameservers: list[str] | None = None, timeout: float = 3.0, lifetime: float = 8.0):
        r = dns.resolver.Resolver(configure=False)
        r.nameservers = nameservers or list(getattr(settings, "DNS_RESOLVERS", ["1.1.1.1", "8.8.8.8", "9.9.9.9"]))
        r.timeout = timeout
        r.lifetime = lifetime
        r.use_edns(0, 0, 1232)
        self._r = r
        self._cache: dict[tuple[str, str], object] = {}
        self._ttl: dict[tuple[str, str], int | None] = {}
        self.queries = 0

    def _query(self, name: str, rtype: str):
        key = (_norm(name), rtype)
        if key in self._cache:
            return self._cache[key]
        if self.queries >= self.MAX_QUERIES:
            raise DnsLookupError("query budget exhausted")
        self.queries += 1
        try:
            answer = self._r.resolve(key[0], rtype, raise_on_no_answer=False)
            result = list(answer.rrset) if answer.rrset is not None else []
            self._ttl[key] = answer.rrset.ttl if answer.rrset is not None else None
        except dns.resolver.NXDOMAIN:
            result = None
        except (dns.resolver.NoNameservers, dns.exception.Timeout, dns.resolver.LifetimeTimeout) as exc:
            raise DnsLookupError(f"{rtype} {key[0]}: {exc.__class__.__name__}") from exc
        except (dns.name.EmptyLabel, dns.name.LabelTooLong, dns.name.NameTooLong) as exc:
            result = None
            _ = exc
        self._cache[key] = result
        return result

    def txt(self, name):
        rrs = self._query(name, "TXT")
        if rrs is None:
            return None
        return [b"".join(r.strings).decode("utf-8", "replace") for r in rrs]

    def mx(self, name):
        rrs = self._query(name, "MX")
        if rrs is None:
            return None
        return sorted((int(r.preference), r.exchange.to_text().rstrip(".").lower()) for r in rrs)

    def addresses(self, name):
        out: list[str] = []
        for rtype in ("A", "AAAA"):
            rrs = self._query(name, rtype)
            if rrs:
                out.extend(r.to_text() for r in rrs)
        return out

    def records(self, name, rtype):
        rrs = self._query(name, rtype)
        if rrs is None:
            return None
        return {"ttl": self._ttl.get((_norm(name), rtype)), "values": sorted(rdata_text(r, rtype) for r in rrs)}

    def authoritative(self, domain):
        return probe_authoritative(domain, self)


class FakeResolver(BaseResolver):
    """In-memory zone: {"example.com": {"TXT": [...], "MX": [(10, "mx.example.com")], "A": [...]}}.

    Names absent from the zone are NXDOMAIN. A value of DnsLookupError for a
    type simulates a timeout.
    """

    def __init__(self, zone: dict[str, dict]):
        self.zone = {_norm(k): v for k, v in zone.items()}
        self.queries = 0

    def _get(self, name, rtype):
        self.queries += 1
        node = self.zone.get(_norm(name))
        if node is None:
            return None
        value = node.get(rtype, [])
        if value is DnsLookupError:
            raise DnsLookupError(f"{rtype} {name}: simulated timeout")
        return value

    def txt(self, name):
        v = self._get(name, "TXT")
        return None if v is None else list(v)

    def mx(self, name):
        v = self._get(name, "MX")
        return None if v is None else sorted((int(p), h.rstrip(".").lower()) for p, h in v)

    def addresses(self, name):
        node = self.zone.get(_norm(name))
        if node is None:
            return []
        return list(node.get("A", [])) + list(node.get("AAAA", []))

    def records(self, name, rtype):
        node = self.zone.get(_norm(name))
        self.queries += 1
        if node is None:
            return None
        value = node.get(rtype, [])
        if value is DnsLookupError:
            raise DnsLookupError(f"{rtype} {name}: simulated timeout")
        if rtype == "MX":
            vals = [f"{int(p)} {h.rstrip('.').lower()}." for p, h in value]
        elif rtype in ("NS", "CNAME"):
            vals = [v.rstrip(".").lower() + "." for v in value]
        elif rtype == "TXT":
            vals = [f'"{v}"' for v in value]
        else:
            vals = [str(v) for v in value]
        ttl = (node.get("TTL") or {}).get(rtype, 3600) if vals else None
        return {"ttl": ttl, "values": sorted(vals)}

    def authoritative(self, domain):
        node = self.zone.get(_norm(domain)) or {}
        if "AUTH" in node:
            return [dict(a) for a in node["AUTH"]]
        soa = node.get("SOA") or []
        serial = int(str(soa[0]).split()[2]) if soa else None
        out = []
        for ns in node.get("NS", []):
            host = ns.rstrip(".").lower()
            ips = (self.zone.get(host) or {}).get("A") or ["192.0.2.53"]
            out.append({"ns": host, "ip": ips[0], "authoritative": True, "serial": serial, "error": ""})
        return out


def rdata_text(r, rtype: str) -> str:
    """Stable text form used for storage and comparison."""
    if rtype == "TXT":
        return '"' + b"".join(r.strings).decode("utf-8", "replace") + '"'
    return r.to_text().lower() if rtype in ("NS", "CNAME", "MX") else r.to_text()


def soa_serial(values: list[str]) -> int | None:
    try:
        return int(values[0].split()[2])
    except (IndexError, ValueError):
        return None


def probe_authoritative(domain: str, resolver, timeout: float = 2.5) -> list[dict]:
    """Ask each delegated name server directly (no recursion) for the zone's SOA.

    Only public addresses are contacted. Shows lame delegation and whether all
    servers serve the same zone version (SOA serial)."""
    import dns.flags
    import dns.message
    import dns.query
    import dns.rcode

    from apps.ssl_monitor.scanner import is_public_ip

    ns = resolver.records(domain, "NS")
    out = []
    for host in [v.rstrip(".") for v in (ns or {}).get("values", [])][:8]:
        entry = {"ns": host, "ip": "", "authoritative": False, "serial": None, "error": ""}
        try:
            ips = [ip for ip in resolver.addresses(host) if is_public_ip(ip)]
        except DnsLookupError as exc:
            entry["error"] = str(exc)
            out.append(entry)
            continue
        if not ips:
            entry["error"] = "Name server has no public address"
            out.append(entry)
            continue
        entry["ip"] = next((ip for ip in ips if ":" not in ip), ips[0])
        try:
            q = dns.message.make_query(domain, "SOA")
            q.flags &= ~dns.flags.RD
            resp = dns.query.udp(q, entry["ip"], timeout=timeout)
            if resp.flags & dns.flags.TC:
                resp = dns.query.tcp(q, entry["ip"], timeout=timeout)
            entry["authoritative"] = bool(resp.flags & dns.flags.AA) and resp.rcode() == dns.rcode.NOERROR
            for rr in resp.answer:
                if rr.rdtype == dns.rdatatype.SOA:
                    entry["serial"] = int(rr[0].serial)
            if not entry["authoritative"]:
                entry["error"] = f"Answered {dns.rcode.to_text(resp.rcode())} without authority"
        except (dns.exception.Timeout, OSError, dns.exception.DNSException) as exc:
            entry["error"] = f"No answer ({exc.__class__.__name__})"
        out.append(entry)
    return out
