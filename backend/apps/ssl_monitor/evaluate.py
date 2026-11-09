"""Turn CertInfo into findings and a status. Pure: no network, used by the
scanner, the demo workspace and tests alike."""

from __future__ import annotations

from datetime import datetime

from apps.dns_monitor.checks.base import CRITICAL, INFO, WARNING, CheckResult

EXPIRY_CRITICAL_DAYS = 7
EXPIRY_WARNING_DAYS = 30


def days_left(not_after_iso: str, now: datetime) -> int | None:
    if not not_after_iso:
        return None
    end = datetime.fromisoformat(not_after_iso)
    return int((end - now).total_seconds() // 86400)


def evaluate(info: dict, now: datetime) -> CheckResult:
    r = CheckResult(check="tls")
    host = info["hostname"]
    days = days_left(info.get("not_after", ""), now)
    r.data = {"days_left": days}

    if days is not None and days < 0:
        r.add(
            "tls_expired",
            CRITICAL,
            f"Certificate expired {abs(days)} day{'s' if abs(days) != 1 else ''} ago",
            "Browsers show a full-page security warning and most visitors leave.",
            "Renew the certificate now and check why automatic renewal did not run.",
        )
    elif days is not None and days <= EXPIRY_CRITICAL_DAYS:
        r.add(
            "tls_expires_soon",
            CRITICAL,
            f"Certificate expires in {days} day{'s' if days != 1 else ''}",
            "If it is not renewed in time, visitors will see a security warning.",
            "Renew it today. If you use Let's Encrypt, check that the renewal job and its DNS/HTTP challenge still work.",
        )
    elif days is not None and days <= EXPIRY_WARNING_DAYS:
        r.add(
            "tls_expiring",
            WARNING,
            f"Certificate expires in {days} days",
            "Renewal should happen soon. Automated certificates usually renew about 30 days before expiry.",
            "Confirm auto-renewal is working, or plan a manual renewal.",
        )

    if not info.get("hostname_match"):
        names = ", ".join(info.get("sans") or [info.get("subject_cn") or "none"])
        r.add(
            "tls_name_mismatch",
            CRITICAL,
            f"Certificate does not cover {host}",
            f"The certificate is issued for: {names}. Browsers will reject it for this name.",
            f"Issue a certificate that includes {host}, or point this name to a server that has one.",
        )
    if info.get("self_signed"):
        r.add(
            "tls_self_signed",
            CRITICAL,
            "Self-signed certificate",
            "No browser trusts a certificate the server signed for itself.",
            "Install a certificate from a public CA such as Let's Encrypt.",
        )
    elif not info.get("trusted") and info.get("hostname_match") and (days is None or days >= 0):
        r.add(
            "tls_untrusted",
            CRITICAL,
            "Certificate chain is not trusted",
            f"Verification failed: {info.get('verify_error') or 'unknown reason'}. Often the intermediate certificate is missing.",
            "Install the full chain (your certificate plus the CA's intermediate) on the server.",
        )

    tls = info.get("tls_version", "")
    if tls in ("TLSv1", "TLSv1.1", "SSLv3"):
        r.add(
            "tls_old_protocol",
            CRITICAL,
            f"Server negotiated {tls}",
            "TLS 1.0 and 1.1 are deprecated and blocked by modern browsers.",
            "Enable TLS 1.2 and 1.3 and disable older versions.",
        )
    sig = (info.get("signature_algorithm") or "").lower()
    if sig in ("sha1", "md5"):
        r.add(
            "tls_weak_signature",
            CRITICAL,
            f"Certificate signed with {sig.upper()}",
            "This signature algorithm is broken and rejected by browsers.",
            "Reissue the certificate with SHA-256.",
        )
    if info.get("key_type") == "RSA" and info.get("key_bits") and info["key_bits"] < 2048:
        r.add(
            "tls_weak_key",
            CRITICAL,
            f"{info['key_bits']}-bit RSA key",
            "Keys under 2048 bits are considered breakable.",
            "Reissue with a 2048-bit (or larger) RSA key or an EC key.",
        )

    hsts = info.get("hsts")
    if info.get("trusted"):
        if hsts is None:
            r.add(
                "tls_no_hsts",
                INFO,
                "HSTS is not enabled",
                "Without HSTS a visitor's first request can be downgraded to plain HTTP.",
                "Add the header Strict-Transport-Security: max-age=31536000 once the whole site works over HTTPS.",
            )
        else:
            try:
                max_age = int(
                    next((p.split("=", 1)[1] for p in hsts.split(";") if p.strip().lower().startswith("max-age")), "0")
                )
            except ValueError:
                max_age = 0
            r.data["hsts_max_age"] = max_age
            if max_age < 15552000:  # 180 days
                r.add(
                    "tls_short_hsts",
                    INFO,
                    "HSTS max-age is short",
                    f"max-age is {max_age} seconds. Six months or more is recommended.",
                    "Raise max-age to 31536000 (one year).",
                )
    r.summary = _summary(r, days, info)
    return r


def _summary(r: CheckResult, days, info) -> str:
    codes = {f.code for f in r.findings}
    if "tls_expired" in codes:
        return "The certificate has expired."
    if "tls_name_mismatch" in codes:
        return "The certificate does not cover this host name."
    if "tls_self_signed" in codes or "tls_untrusted" in codes:
        return "Browsers do not trust this certificate."
    issuer = info.get("issuer_org") or info.get("issuer") or "a public CA"
    if days is None:
        return f"Certificate issued by {issuer}."
    return f"Valid certificate from {issuer}, {days} day{'s' if days != 1 else ''} left."
