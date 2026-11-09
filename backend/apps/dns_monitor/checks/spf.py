"""SPF (RFC 7208) checks: presence, uniqueness, syntax, 10-lookup limit, loops, 'all'."""

from __future__ import annotations

import ipaddress

from ..resolver import BaseResolver, DnsLookupError
from .base import CRITICAL, INFO, WARNING, CheckResult

LOOKUP_LIMIT = 10
VOID_LIMIT = 2
LOOKUP_MECHS = {"include", "a", "mx", "ptr", "exists"}
NO_LOOKUP_MECHS = {"ip4", "ip6", "all"}
QUALIFIERS = "+-~?"


def spf_records(txts: list[str] | None) -> list[str]:
    out = []
    for t in txts or []:
        low = t.strip().lower()
        if low == "v=spf1" or low.startswith("v=spf1 "):
            out.append(t.strip())
    return out


def _split(term: str) -> tuple[str, str, str | None]:
    """Return (qualifier, mechanism/modifier name, value)."""
    q = "+"
    if term and term[0] in QUALIFIERS:
        q, term = term[0], term[1:]
    if "=" in term and ":" not in term.split("=", 1)[0]:
        name, value = term.split("=", 1)  # modifier
        return q, name.lower() + "=", value
    if ":" in term:
        name, value = term.split(":", 1)
    elif "/" in term:
        name, value = term.split("/", 1)[0], None
    else:
        name, value = term, None
    return q, name.lower(), value


class _Walker:
    def __init__(self, resolver: BaseResolver):
        self.r = resolver
        self.lookups = 0
        self.voids = 0
        self.errors: list[tuple[str, str]] = []  # (code, message)
        self.loops: list[str] = []
        self.includes: list[str] = []

    def walk(self, domain: str, record: str, chain: tuple[str, ...], depth: int = 0):
        if depth > 10:
            self.errors.append(("spf_depth", f"SPF include chain deeper than 10 levels at {domain}."))
            return
        terms = record.split()[1:]
        for term in terms:
            q, name, value = _split(term)
            if name in LOOKUP_MECHS:
                self.lookups += 1
                if name == "include":
                    if not value:
                        self.errors.append(("spf_syntax", "An include mechanism has no domain."))
                        continue
                    target = value.lower().rstrip(".")
                    self.includes.append(target)
                    if target in chain:
                        self.loops.append(target)
                        continue
                    self._follow(target, chain, depth, "include")
                elif name == "mx" and value is None:
                    pass
            elif name == "redirect=":
                if any(_split(t)[1] == "all" for t in terms):
                    continue  # redirect is ignored when 'all' is present
                self.lookups += 1
                target = (value or "").lower().rstrip(".")
                if target in chain:
                    self.loops.append(target)
                    continue
                self._follow(target, chain, depth, "redirect")
            elif name in NO_LOOKUP_MECHS or name == "exp=" or name.endswith("="):
                continue
            else:
                self.errors.append(("spf_syntax", f"Unknown SPF term '{term}' in the record for {domain}."))

    def _follow(self, target: str, chain, depth, kind):
        txts = self.r.txt(target)
        recs = spf_records(txts)
        if txts is None or not recs:
            self.voids += 1
            self.errors.append(("spf_include_missing", f"The {kind} target {target} has no SPF record."))
            return
        if len(recs) > 1:
            self.errors.append(
                ("spf_include_multiple", f"The {kind} target {target} publishes more than one SPF record.")
            )
        self.walk(target, recs[0], chain + (target,), depth + 1)


def check_spf(domain: str, resolver: BaseResolver) -> CheckResult:
    res = CheckResult("spf")
    try:
        txts = resolver.txt(domain)
        recs = spf_records(txts)
        if not recs:
            res.summary = "No SPF record is published."
            res.add(
                "spf_missing",
                CRITICAL,
                "No SPF record",
                "Receivers cannot tell which servers may send mail for this domain, so spoofed mail is harder to reject.",
                f'Publish one TXT record on {domain} such as "v=spf1 include:<your mail provider> -all".',
            )
            return res
        res.record = recs[0]
        if len(recs) > 1:
            res.add(
                "spf_multiple",
                CRITICAL,
                "More than one SPF record",
                f"{len(recs)} SPF records were found. Receivers treat this as a permanent error and SPF fails for every message.",
                "Merge them into a single TXT record that starts with v=spf1.",
            )
            res.data["records"] = recs

        w = _Walker(resolver)
        w.walk(domain.lower(), recs[0], (domain.lower(),))
        terms = recs[0].split()[1:]
        all_q = next((_split(t)[0] for t in terms if _split(t)[1] == "all"), None)
        has_redirect = any(_split(t)[1] == "redirect=" for t in terms)
        res.data.update(
            lookups=w.lookups, lookup_limit=LOOKUP_LIMIT, void_lookups=w.voids, includes=w.includes, all=all_q
        )

        # Syntax of the top-level record: ip4/ip6 networks and repeated terms.
        seen: dict[str, int] = {}
        for t in terms:
            q, name, value = _split(t)
            key = (name + ":" + (value or "")).lower()
            seen[key] = seen.get(key, 0) + 1
            if name in ("ip4", "ip6"):
                try:
                    net = ipaddress.ip_network((value or "").strip(), strict=False)
                    if (name == "ip4") != (net.version == 4):
                        raise ValueError
                except ValueError:
                    w.errors.append(("spf_syntax", f"'{t}' is not a valid {name} address or network."))
        dupes = [k.rstrip(":") for k, n in seen.items() if n > 1]
        if dupes:
            res.add(
                "spf_duplicate",
                WARNING,
                "Repeated SPF terms",
                f"These appear more than once: {', '.join(dupes)}. Repeats waste DNS lookups and usually mean the record was edited by hand.",
                "Keep one copy of each term.",
            )

        for code, msg in w.errors:
            sev = CRITICAL if code in ("spf_syntax", "spf_include_missing", "spf_depth") else WARNING
            res.add(
                code,
                sev,
                "SPF error in the include chain" if code != "spf_syntax" else "SPF syntax error",
                msg,
                "Correct or remove the term so receivers can evaluate the record.",
            )
        for target in sorted(set(w.loops)):
            res.add(
                "spf_loop",
                CRITICAL,
                "SPF include loop",
                f"{target} is included again from inside its own chain.",
                "Remove the circular include.",
            )
        if w.lookups > LOOKUP_LIMIT:
            res.add(
                "spf_too_many_lookups",
                CRITICAL,
                "Too many DNS lookups",
                f"Evaluating this record needs {w.lookups} DNS lookups; the limit is {LOOKUP_LIMIT}. Receivers return a permanent error.",
                "Remove unused includes, or replace some includes with ip4:/ip6: ranges.",
            )
        elif w.lookups >= LOOKUP_LIMIT - 1:
            res.add(
                "spf_near_limit",
                WARNING,
                "Close to the DNS lookup limit",
                f"{w.lookups} of {LOOKUP_LIMIT} lookups are used. Adding one more service will break SPF.",
                "Review includes before adding new sending services.",
            )
        if w.voids > VOID_LIMIT:
            res.add(
                "spf_void_lookups",
                WARNING,
                "Too many empty lookups",
                f"{w.voids} lookups return no record; more than {VOID_LIMIT} is a permanent error for many receivers.",
                "Remove includes that point to domains without SPF.",
            )
        if any(_split(t)[1] == "ptr" for t in terms):
            res.add(
                "spf_ptr",
                WARNING,
                "Uses the deprecated ptr mechanism",
                "ptr is slow and unreliable, and many receivers ignore it.",
                "Replace ptr with ip4:/ip6: or include:.",
            )

        if all_q == "+":
            res.add(
                "spf_plus_all",
                CRITICAL,
                "Record allows any server (+all)",
                "+all authorises every server on the internet to send as this domain.",
                "Change +all to -all or ~all.",
            )
        elif all_q == "?":
            res.add(
                "spf_neutral_all",
                WARNING,
                "Ends in ?all (neutral)",
                "Neutral gives receivers no guidance about unlisted servers.",
                "Use ~all while testing, then -all.",
            )
        elif all_q is None and not has_redirect:
            res.add(
                "spf_no_all",
                WARNING,
                "No 'all' mechanism",
                "Without an all mechanism the default result for unlisted servers is neutral.",
                "End the record with ~all or -all.",
            )
        elif all_q == "~":
            res.add(
                "spf_softfail",
                INFO,
                "Ends in ~all (soft fail)",
                "Unlisted servers soft fail. This is normal while DMARC is enforcing.",
                "Move to -all once all legitimate senders are listed.",
            )

        if res.status == "pass":
            res.summary = f"Valid SPF record using {w.lookups} of {LOOKUP_LIMIT} DNS lookups."
        elif res.status == "warn":
            res.summary = "SPF record works but needs attention."
        else:
            res.summary = "SPF is broken or unsafe; receivers may reject or misjudge mail."
    except DnsLookupError as exc:
        res.error = True
        res.summary = "DNS lookup timed out; the check will run again on the next scan."
        res.data["error"] = str(exc)
    return res
