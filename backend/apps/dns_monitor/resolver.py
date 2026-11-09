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


class LiveResolver(BaseResolver):
    MAX_QUERIES = 60  # hard ceiling per scan (SPF recursion, DKIM selectors...)

    def __init__(self, nameservers: list[str] | None = None, timeout: float = 3.0, lifetime: float = 8.0):
        r = dns.resolver.Resolver(configure=False)
        r.nameservers = nameservers or list(getattr(settings, "DNS_RESOLVERS", ["1.1.1.1", "8.8.8.8", "9.9.9.9"]))
        r.timeout = timeout
        r.lifetime = lifetime
        r.use_edns(0, 0, 1232)
        self._r = r
        self._cache: dict[tuple[str, str], object] = {}
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
