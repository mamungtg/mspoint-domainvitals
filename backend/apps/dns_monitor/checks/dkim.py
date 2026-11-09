"""DKIM (RFC 6376) key discovery for known and user-supplied selectors."""

from __future__ import annotations

import base64
import binascii
import re

from ..resolver import BaseResolver, DnsLookupError
from .base import CRITICAL, INFO, WARNING, CheckResult, parse_tags

# Selectors used by common mail services. DNS cannot list selectors, so we probe.
COMMON_SELECTORS = [
    "google",  # Google Workspace
    "selector1",
    "selector2",  # Microsoft 365
    "zmail",  # Zoho Mail
    "default",
    "k1",
    "k2",
    "s1",
    "s2",
    "mail",
    "dkim",
]
SELECTOR_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?$")


def estimate_rsa_bits(p: str) -> int | None:
    """Estimate RSA modulus size from the DER SubjectPublicKeyInfo length."""
    try:
        der = base64.b64decode(re.sub(r"\s+", "", p), validate=True)
    except (binascii.Error, ValueError):
        return None
    n = len(der)
    if n < 100:
        return 512
    if n < 200:
        return 1024
    if n < 400:
        return 2048
    return 4096


def check_dkim(domain: str, resolver: BaseResolver, selectors: list[str] | None = None) -> CheckResult:
    res = CheckResult("dkim")
    wanted = []
    for s in list(selectors or []) + COMMON_SELECTORS:
        s = s.strip().lower()
        if SELECTOR_RE.match(s) and s not in wanted:
            wanted.append(s)
    found = []
    timeouts = 0
    for sel in wanted:
        try:
            txts = resolver.txt(f"{sel}._domainkey.{domain}")
        except DnsLookupError:
            timeouts += 1
            continue
        recs = [t for t in (txts or []) if "p=" in t.replace(" ", "")]
        if not recs:
            continue
        tags = parse_tags(recs[0])
        key_type = tags.get("k", "rsa").lower()
        p = tags.get("p", "")
        bits = 256 if key_type == "ed25519" else (estimate_rsa_bits(p) if p else None)
        found.append({"selector": sel, "key_type": key_type, "bits": bits, "revoked": p == "", "record": recs[0]})

    res.data.update(selectors_checked=wanted, selectors=found)
    if timeouts and not found and timeouts == len(wanted):
        res.error = True
        res.summary = "DNS lookups timed out; the check will run again on the next scan."
        return res

    active = [k for k in found if not k["revoked"]]
    if not active:
        res.add(
            "dkim_not_found",
            WARNING,
            "No DKIM key found",
            f"No published key was found for the {len(wanted)} selectors checked. DKIM may still be set up under another selector.",
            "Add your mail provider's selector in this domain's settings, or enable DKIM signing with your provider.",
        )
        res.summary = "No DKIM key found for the selectors checked."
        return res

    res.record = active[0]["record"]
    for k in found:
        if k["revoked"]:
            res.add(
                "dkim_revoked",
                INFO,
                f"Selector {k['selector']} is revoked",
                "The key is published with an empty p= value, which means it is retired.",
                "Remove it once no mail uses it.",
            )
        elif k["key_type"] == "rsa" and k["bits"] is not None and k["bits"] < 1024:
            res.add(
                "dkim_weak_key",
                CRITICAL,
                f"Selector {k['selector']} uses a key under 1024 bits",
                "Keys this short can be broken and many receivers reject them.",
                "Rotate to a 2048-bit key.",
            )
        elif k["key_type"] == "rsa" and k["bits"] == 1024:
            res.add(
                "dkim_1024",
                WARNING,
                f"Selector {k['selector']} uses a 1024-bit key",
                "1024-bit RSA is below current recommendations.",
                "Rotate to a 2048-bit key.",
            )
        elif k["bits"] is None:
            res.add(
                "dkim_bad_key",
                CRITICAL,
                f"Selector {k['selector']} has an unreadable key",
                "The p= value is not valid base64.",
                "Republish the key exactly as your provider gives it.",
            )
    names = ", ".join(k["selector"] for k in active)
    res.summary = f"DKIM key{'s' if len(active) > 1 else ''} found for {names}."
    return res
