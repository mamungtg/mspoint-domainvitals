"""Normalise and validate customer-entered domain names."""

import ipaddress
import re
from urllib.parse import urlsplit

LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
TLD_RE = re.compile(r"^(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")


class InvalidDomain(ValueError):
    pass


def normalize_domain(raw: str) -> str:
    """Accept 'Example.COM', 'https://www.example.com/path', 'bücher.de' -> ASCII lower-case host.

    Rejects IP addresses, single labels, wildcards and over-long names.
    """
    value = (raw or "").strip()
    if not value:
        raise InvalidDomain("Enter a domain name.")
    if "://" in value:
        value = urlsplit(value).hostname or ""
    value = value.split("/")[0].split("?")[0].strip().rstrip(".")
    if "@" in value:
        value = value.split("@")[-1]
    if not value:
        raise InvalidDomain("Enter a domain name.")
    try:
        ipaddress.ip_address(value.strip("[]"))
        raise InvalidDomain("Enter a domain name, not an IP address.")
    except ValueError:
        pass
    if "*" in value or " " in value:
        raise InvalidDomain("Enter a single domain such as example.com.")
    try:
        ascii_name = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise InvalidDomain("This domain name contains characters that are not allowed.") from exc
    if len(ascii_name) > 253:
        raise InvalidDomain("This domain name is too long.")
    labels = ascii_name.split(".")
    if len(labels) < 2:
        raise InvalidDomain("Enter a full domain such as example.com.")
    if not all(LABEL_RE.match(lbl) for lbl in labels) or not TLD_RE.match(labels[-1]):
        raise InvalidDomain("This is not a valid domain name.")
    return ascii_name
