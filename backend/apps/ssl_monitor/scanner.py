"""SSL/TLS certificate scanner.

Security: the hostname comes from users, so we resolve it ourselves and connect
only to public, globally routable IP addresses (no loopback, private, link-local,
CGNAT, multicast or reserved ranges). This blocks SSRF into the server's own
network, and DNS rebinding cannot help because we connect to the IP we vetted.
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import certifi
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtensionOID, NameOID

CONNECT_TIMEOUT = 8.0


class ScanBlocked(Exception):
    """Target is not allowed (resolves to a non-public address)."""


class ScanFailed(Exception):
    """Could not complete a TLS handshake at all."""


@dataclass
class CertInfo:
    hostname: str
    port: int
    ip: str = ""
    tls_version: str = ""
    cipher: str = ""
    subject_cn: str = ""
    sans: list[str] = field(default_factory=list)
    issuer: str = ""
    issuer_org: str = ""
    serial: str = ""
    not_before: str = ""  # ISO 8601
    not_after: str = ""
    signature_algorithm: str = ""
    key_type: str = ""
    key_bits: int | None = None
    self_signed: bool = False
    trusted: bool = False
    verify_error: str = ""
    hostname_match: bool = False
    hsts: str | None = None  # Strict-Transport-Security header value, if any

    def to_dict(self) -> dict:
        return asdict(self)


def is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def resolve_public(hostname: str, port: int) -> str:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ScanFailed(f"{hostname} does not resolve") from exc
    ips = list(dict.fromkeys(i[4][0] for i in infos))
    public = [ip for ip in ips if is_public_ip(ip)]
    if not public:
        raise ScanBlocked(f"{hostname} resolves only to non-public addresses")
    return _prefer_ipv4(public)


def _prefer_ipv4(ips: list[str]) -> str:
    v4 = [ip for ip in ips if ":" not in ip]
    return (v4 or ips)[0]


def resolve_any(hostname: str, port: int) -> str:
    """Tests only: resolve without the public-address check (IPv4 first, like resolve_public)."""
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ScanFailed(f"{hostname} does not resolve") from exc
    return _prefer_ipv4(list(dict.fromkeys(i[4][0] for i in infos)))


def _connect(ip: str, port: int, hostname: str, ctx: ssl.SSLContext, timeout: float):
    raw = socket.create_connection((ip, port), timeout=timeout)
    try:
        return ctx.wrap_socket(raw, server_hostname=hostname)
    except Exception:
        raw.close()
        raise


def _hsts(sock: ssl.SSLSocket, hostname: str) -> str | None:
    try:
        sock.sendall(
            f"HEAD / HTTP/1.1\r\nHost: {hostname}\r\nUser-Agent: DomainVitals-TLS-Check\r\nConnection: close\r\n\r\n".encode()
        )
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 16384:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        for line in data.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n")[1:]:
            name, _, value = line.partition(":")
            if name.strip().lower() == "strict-transport-security":
                return value.strip()
    except (OSError, ssl.SSLError):
        return None
    return None


def _name_attr(name: x509.Name, oid) -> str:
    vals = name.get_attributes_for_oid(oid)
    return str(vals[0].value) if vals else ""


def parse_certificate(der: bytes, info: CertInfo) -> CertInfo:
    cert = x509.load_der_x509_certificate(der)
    info.subject_cn = _name_attr(cert.subject, NameOID.COMMON_NAME)
    info.issuer = _name_attr(cert.issuer, NameOID.COMMON_NAME) or cert.issuer.rfc4514_string()
    info.issuer_org = _name_attr(cert.issuer, NameOID.ORGANIZATION_NAME)
    info.serial = format(cert.serial_number, "x")
    info.not_before = cert.not_valid_before_utc.isoformat()
    info.not_after = cert.not_valid_after_utc.isoformat()
    info.self_signed = cert.issuer == cert.subject
    try:
        info.sans = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        ).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        info.sans = []
    algo = cert.signature_hash_algorithm
    info.signature_algorithm = algo.name if isinstance(algo, hashes.HashAlgorithm) else "unknown"
    key = cert.public_key()
    if isinstance(key, rsa.RSAPublicKey):
        info.key_type, info.key_bits = "RSA", key.key_size
    elif isinstance(key, ec.EllipticCurvePublicKey):
        info.key_type, info.key_bits = "EC", key.curve.key_size
    else:
        info.key_type = key.__class__.__name__.replace("PublicKey", "")
    return info


def hostname_matches(hostname: str, names: list[str]) -> bool:
    host = hostname.lower().rstrip(".")
    for n in names:
        n = n.lower().rstrip(".")
        if n == host:
            return True
        if n.startswith("*.") and host.count(".") == n.count(".") and host.endswith(n[1:]):
            return True
    return False


def scan(
    hostname: str,
    port: int = 443,
    *,
    timeout: float = CONNECT_TIMEOUT,
    allow_private: bool = False,
    cafile: str | None = None,
) -> CertInfo:
    """Handshake twice: once with full verification (is it trusted?) and once
    without (so we can still read an expired or self-signed certificate)."""
    info = CertInfo(hostname=hostname, port=port)
    info.ip = resolve_any(hostname, port) if allow_private else resolve_public(hostname, port)

    # 1. Verified handshake
    vctx = ssl.create_default_context(cafile=cafile or certifi.where())
    try:
        with _connect(info.ip, port, hostname, vctx, timeout) as s:
            info.trusted = True
            info.hostname_match = True
            info.tls_version = s.version() or ""
            info.cipher = (s.cipher() or ("",))[0]
            der = s.getpeercert(binary_form=True)
            info.hsts = _hsts(s, hostname)
        return parse_certificate(der, info)
    except ssl.SSLCertVerificationError as exc:
        info.verify_error = (exc.verify_message or str(exc)).strip()
    except (TimeoutError, ConnectionError, OSError) as exc:
        if not isinstance(exc, ssl.SSLError):
            raise ScanFailed(f"Could not connect to {hostname}:{port} ({exc.__class__.__name__})") from exc
        info.verify_error = str(exc)

    # 2. Unverified handshake to read the certificate anyway
    uctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    uctx.check_hostname = False
    uctx.verify_mode = ssl.CERT_NONE
    try:
        with _connect(info.ip, port, hostname, uctx, timeout) as s:
            info.tls_version = s.version() or ""
            info.cipher = (s.cipher() or ("",))[0]
            der = s.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as exc:
        raise ScanFailed(f"TLS handshake with {hostname}:{port} failed ({exc.__class__.__name__})") from exc
    if not der:
        raise ScanFailed(f"{hostname}:{port} did not present a certificate")
    parse_certificate(der, info)
    info.hostname_match = hostname_matches(hostname, info.sans or [info.subject_cn])
    return info


def now_utc() -> datetime:
    return datetime.now(UTC)
