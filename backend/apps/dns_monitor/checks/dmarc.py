"""DMARC (RFC 7489) checks."""

from __future__ import annotations

from ..resolver import BaseResolver, DnsLookupError
from .base import CRITICAL, INFO, WARNING, CheckResult, parse_tags

POLICIES = {"none", "quarantine", "reject"}


def dmarc_records(txts: list[str] | None) -> list[str]:
    return [t.strip() for t in (txts or []) if t.strip().lower().replace(" ", "").startswith("v=dmarc1")]


def check_dmarc(domain: str, resolver: BaseResolver) -> CheckResult:
    res = CheckResult("dmarc")
    name = f"_dmarc.{domain}"
    try:
        recs = dmarc_records(resolver.txt(name))
        if not recs:
            res.summary = "No DMARC record is published."
            res.data["policy"] = None
            res.add(
                "dmarc_missing",
                CRITICAL,
                "No DMARC record",
                "Without DMARC, receivers apply their own rules to mail that fails SPF and DKIM, and you get no reports.",
                f'Publish a TXT record at {name}: "v=DMARC1; p=none; rua=mailto:dmarc@{domain}", then move to quarantine and reject.',
            )
            return res
        res.record = recs[0]
        if len(recs) > 1:
            res.add(
                "dmarc_multiple",
                CRITICAL,
                "More than one DMARC record",
                "Receivers ignore DMARC entirely when several records exist.",
                f"Keep a single TXT record at {name}.",
            )
        tags = parse_tags(recs[0])
        p = tags.get("p", "").lower()
        sp = tags.get("sp", "").lower() or None
        rua = [u.strip() for u in tags.get("rua", "").split(",") if u.strip()]
        ruf = [u.strip() for u in tags.get("ruf", "").split(",") if u.strip()]
        pct_raw = tags.get("pct", "100")
        try:
            pct = int(pct_raw)
        except ValueError:
            pct = None
        res.data.update(
            policy=p if p in POLICIES else None,
            subdomain_policy=sp,
            pct=pct,
            rua=rua,
            ruf=ruf,
            adkim=tags.get("adkim", "r"),
            aspf=tags.get("aspf", "r"),
        )

        if p not in POLICIES:
            res.add(
                "dmarc_bad_policy",
                CRITICAL,
                "Missing or invalid policy",
                f"The p= tag is {'missing' if not p else repr(p)}; receivers treat the record as invalid.",
                "Set p=none, p=quarantine or p=reject.",
            )
        elif p == "none":
            res.add(
                "dmarc_p_none",
                WARNING,
                "Policy is p=none (monitoring only)",
                "Mail that fails authentication is still delivered, so this domain can be spoofed.",
                "After reviewing reports, move to p=quarantine and then p=reject.",
            )
        elif p == "quarantine":
            res.add(
                "dmarc_p_quarantine",
                INFO,
                "Policy is p=quarantine",
                "Failing mail goes to spam. This is good protection.",
                "Move to p=reject when reports look clean.",
            )

        if sp == "none" and p in ("quarantine", "reject"):
            res.add(
                "dmarc_sp_none",
                WARNING,
                "Subdomains are not protected",
                "sp=none lets attackers spoof any subdomain even though the main domain is enforced.",
                "Remove sp= or set it to quarantine or reject.",
            )
        if pct is None or not (0 <= pct <= 100):
            res.add(
                "dmarc_bad_pct",
                WARNING,
                "Invalid pct value",
                f"pct={pct_raw} is not a number from 0 to 100.",
                "Use pct=100.",
            )
        elif pct < 100 and p in ("quarantine", "reject"):
            res.add(
                "dmarc_partial_pct",
                WARNING,
                f"Policy applies to {pct}% of mail",
                f"Only {pct}% of failing messages get the {p} policy.",
                "Raise pct to 100 when ready.",
            )
        if not rua:
            res.add(
                "dmarc_no_rua",
                WARNING,
                "No aggregate reports requested",
                "Without rua=, you cannot see who sends mail as this domain or whether it passes.",
                f"Add rua=mailto:<reporting address> to the record at {name}.",
            )
        elif any(not u.lower().startswith("mailto:") for u in rua):
            res.add(
                "dmarc_bad_rua",
                WARNING,
                "Report address is not a mailto: URI",
                "rua addresses must start with mailto:.",
                "Correct the rua tag.",
            )
        for k in ("adkim", "aspf"):
            if tags.get(k, "r").lower() not in ("r", "s"):
                res.add(
                    f"dmarc_bad_{k}", WARNING, f"Invalid {k} value", f"{k} must be r or s.", f"Set {k}=r or remove it."
                )

        res.summary = {
            "pass": f"DMARC is enforced with p={p}.",
            "warn": f"DMARC is published (p={p or 'invalid'}) but needs attention.",
            "fail": "DMARC is published but invalid.",
        }[res.status]
    except DnsLookupError as exc:
        res.error = True
        res.summary = "DNS lookup timed out; the check will run again on the next scan."
        res.data["error"] = str(exc)
    return res
