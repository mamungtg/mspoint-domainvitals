"""Name the service behind a sending IP so reports read "Google Workspace"
instead of "209.85.220.41".

The reverse DNS name is the main signal. When it is missing, the domain that
signed the message with DKIM is used as a hint. Lookups are cached in
SourceIp for 30 days.
"""

from __future__ import annotations

import ipaddress
from datetime import timedelta

import dns.exception
import dns.resolver
import dns.reversename
from django.utils import timezone

from .models import SourceIp

REFRESH = timedelta(days=30)

# Suffix of the PTR name (or a DKIM signing domain) -> service name.
PROVIDERS: list[tuple[str, str]] = [
    ("google.com", "Google"),
    ("googlemail.com", "Google"),
    ("outlook.com", "Microsoft 365"),
    ("protection.outlook.com", "Microsoft 365"),
    ("onmicrosoft.com", "Microsoft 365"),
    ("hotmail.com", "Microsoft 365"),
    ("zoho.com", "Zoho Mail"),
    ("zohomail.com", "Zoho Mail"),
    ("zoho.eu", "Zoho Mail"),
    ("zoho.in", "Zoho Mail"),
    ("amazonses.com", "Amazon SES"),
    ("sendgrid.net", "SendGrid"),
    ("sendgrid.info", "SendGrid"),
    ("mailgun.net", "Mailgun"),
    ("mailgun.org", "Mailgun"),
    ("mcsv.net", "Mailchimp"),
    ("rsgsv.net", "Mailchimp"),
    ("mcdlv.net", "Mailchimp"),
    ("mailchimpapp.net", "Mailchimp"),
    ("mandrillapp.com", "Mailchimp Transactional"),
    ("sparkpostmail.com", "SparkPost"),
    ("mtasv.net", "Postmark"),
    ("postmarkapp.com", "Postmark"),
    ("hubspotemail.net", "HubSpot"),
    ("hubspot.com", "HubSpot"),
    ("exacttarget.com", "Salesforce Marketing Cloud"),
    ("salesforce.com", "Salesforce"),
    ("sendinblue.com", "Brevo"),
    ("brevo.com", "Brevo"),
    ("protonmail.ch", "Proton Mail"),
    ("yahoo.com", "Yahoo"),
    ("icloud.com", "iCloud Mail"),
    ("apple.com", "iCloud Mail"),
    ("mimecast.com", "Mimecast"),
    ("pphosted.com", "Proofpoint"),
    ("messagelabs.com", "Broadcom Email Security"),
    ("freshdesk.com", "Freshdesk"),
    ("zendesk.com", "Zendesk"),
    ("intercom-mail.com", "Intercom"),
    ("klaviyomail.com", "Klaviyo"),
    ("constantcontact.com", "Constant Contact"),
    ("secureserver.net", "GoDaddy"),
    ("ovh.net", "OVHcloud"),
    ("hostinger.com", "Hostinger"),
]


def provider_for(name: str) -> str:
    name = (name or "").rstrip(".").lower()
    for suffix, label in PROVIDERS:
        if name == suffix or name.endswith("." + suffix):
            return label
    return ""


def reverse_name(ip: str, timeout: float = 2.0) -> str:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    if not addr.is_global:
        return ""
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = ["1.1.1.1", "8.8.8.8"]
    r.lifetime = timeout
    try:
        ans = r.resolve(dns.reversename.from_address(ip), "PTR")
    except (dns.exception.DNSException, OSError):
        return ""
    return str(ans[0]).rstrip(".").lower()[:253] if ans else ""


def label(ip: str, ptr: str, provider: str, dkim_domains=()) -> str:
    """What to call a source in the UI."""
    if provider:
        return provider
    for d in dkim_domains:
        p = provider_for(d)
        if p:
            return p
    if ptr:
        parts = ptr.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else ptr
    return "Unknown sender"


def identify(ips, lookup=None) -> None:
    """Fill or refresh SourceIp rows for the given addresses."""
    lookup = lookup or reverse_name
    now = timezone.now()
    ips = set(ips)
    fresh = set(SourceIp.objects.filter(ip__in=ips, looked_up_at__gte=now - REFRESH).values_list("ip", flat=True))
    for ip in sorted(ips - fresh)[:500]:
        ptr = lookup(ip)
        SourceIp.objects.update_or_create(
            ip=ip, defaults={"ptr": ptr, "provider": provider_for(ptr), "looked_up_at": now}
        )
