import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.utils import timezone

from apps.domains.demo import ensure_demo_workspace
from apps.domains.models import Domain
from apps.ssl_monitor import scanner
from apps.ssl_monitor.evaluate import evaluate
from apps.ssl_monitor.models import MonitoredHost, SslScan
from apps.ssl_monitor.reports import summarize
from apps.ssl_monitor.services import execute, in_scope, queue

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def info(**kw):
    base = {
        "hostname": "acme.com",
        "port": 443,
        "tls_version": "TLSv1.3",
        "subject_cn": "acme.com",
        "sans": ["acme.com"],
        "issuer": "R11",
        "issuer_org": "Let's Encrypt",
        "not_after": (NOW + timedelta(days=80)).isoformat(),
        "signature_algorithm": "sha256",
        "key_type": "RSA",
        "key_bits": 2048,
        "self_signed": False,
        "trusted": True,
        "verify_error": "",
        "hostname_match": True,
        "hsts": "max-age=31536000",
    }
    base.update(kw)
    return base


def codes(r):
    return {f.code for f in r.findings}


# ---------- evaluator ----------------------------------------------------------


def test_healthy_certificate_passes():
    r = evaluate(info(), NOW)
    assert r.status == "pass" and not r.findings and r.data["days_left"] == 80


@pytest.mark.parametrize(
    "days,code,status", [(20, "tls_expiring", "warn"), (5, "tls_expires_soon", "fail"), (-2, "tls_expired", "fail")]
)
def test_expiry_thresholds(days, code, status):
    r = evaluate(info(not_after=(NOW + timedelta(days=days)).isoformat(), trusted=days >= 0), NOW)
    assert code in codes(r) and r.status == status
    assert "tls_untrusted" not in codes(r)  # expiry is the reason, not a chain problem


def test_name_mismatch_self_signed_and_weak_crypto():
    r = evaluate(info(hostname="www.acme.com", hostname_match=False, trusted=False), NOW)
    assert "tls_name_mismatch" in codes(r) and "tls_untrusted" not in codes(r)
    r = evaluate(info(self_signed=True, trusted=False), NOW)
    assert codes(r) >= {"tls_self_signed"} and "tls_untrusted" not in codes(r)
    r = evaluate(info(trusted=False, verify_error="unable to get local issuer certificate"), NOW)
    assert "tls_untrusted" in codes(r)
    r = evaluate(info(tls_version="TLSv1.1", signature_algorithm="sha1", key_bits=1024), NOW)
    assert codes(r) >= {"tls_old_protocol", "tls_weak_signature", "tls_weak_key"} and r.status == "fail"


def test_hsts_advice():
    assert "tls_no_hsts" in codes(evaluate(info(hsts=None), NOW))
    assert "tls_short_hsts" in codes(evaluate(info(hsts="max-age=300"), NOW))
    assert evaluate(info(hsts=None), NOW).status == "pass"  # advice only


def test_wildcard_matching():
    assert scanner.hostname_matches("www.acme.com", ["*.acme.com"])
    assert not scanner.hostname_matches("a.b.acme.com", ["*.acme.com"])
    assert not scanner.hostname_matches("acme.com", ["*.acme.com"])


# ---------- SSRF guard ----------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.12.11",
        "172.17.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "::1",
        "fd00::1",
        "::ffff:127.0.0.1",
        "0.0.0.0",
        "224.0.0.1",
    ],
)
def test_private_addresses_are_blocked(ip):
    assert not scanner.is_public_ip(ip)


def test_public_addresses_allowed():
    assert scanner.is_public_ip("1.1.1.1") and scanner.is_public_ip("2606:4700:4700::1111")


def test_hostname_resolving_to_private_ip_is_refused(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.0.0.7", 443))])
    with pytest.raises(scanner.ScanBlocked):
        scanner.scan("internal.acme.com")


def test_scope_rules():
    assert in_scope("acme.com", "acme.com") and in_scope("mail.acme.com", "acme.com")
    assert not in_scope("evilacme.com", "acme.com") and not in_scope("acme.com.evil.net", "acme.com")


# ---------- real handshake against a local self-signed server --------------------


def _self_signed(cn, days):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(cn)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return cert, key


@pytest.fixture
def tls_server(tmp_path):
    cert, key = _self_signed("localhost", 12)
    cp, kp = tmp_path / "c.pem", tmp_path / "k.pem"
    cp.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    kp.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cp, kp)
    srv = socket.create_server(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    stop = threading.Event()

    def serve():
        srv.settimeout(0.5)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except TimeoutError:
                continue
            try:
                with ctx.wrap_socket(conn, server_side=True) as s:
                    s.settimeout(2)
                    try:
                        s.recv(1024)
                        s.sendall(b"HTTP/1.1 200 OK\r\nStrict-Transport-Security: max-age=600\r\n\r\n")
                    except OSError:
                        pass
            except (ssl.SSLError, OSError):
                pass  # verified client rejects the self-signed cert

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    yield port
    stop.set()
    t.join(2)
    srv.close()


def test_localhost_prefers_ipv4_like_ci_runners(monkeypatch):
    """GitHub runners resolve localhost to ::1 first; the scanner must still pick IPv4."""
    real = socket.getaddrinfo
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda h, p, *a, **k: (
            [
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", p, 0, 0)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", p)),
            ]
            if h == "localhost"
            else real(h, p, *a, **k)
        ),
    )
    assert scanner.resolve_any("localhost", 443) == "127.0.0.1"


def test_real_handshake_reads_untrusted_certificate(tls_server):
    i = scanner.scan("localhost", tls_server, allow_private=True, timeout=3)
    assert i.self_signed and not i.trusted and i.hostname_match
    assert i.subject_cn == "localhost" and i.key_type == "RSA" and i.key_bits == 2048
    assert i.tls_version in ("TLSv1.2", "TLSv1.3")
    r = evaluate(i.to_dict(), timezone.now())
    assert {"tls_self_signed", "tls_expiring"} <= codes(r) and r.status == "fail"


def test_unreachable_port_fails_cleanly():
    with pytest.raises(scanner.ScanFailed):
        scanner.scan("localhost", 1, allow_private=True, timeout=1)


# ---------- service, API and isolation ---------------------------------------------


@pytest.fixture
def verified_domain(make_user, make_org):
    owner = make_user("owner@example.com")
    org = make_org(owner)
    d = Domain.objects.create(organization=org, name="acme.com", verified_at=timezone.now())
    return owner, org, d


def test_execute_stores_result_and_failure(verified_domain):
    _, _, d = verified_domain
    host = MonitoredHost.objects.create(domain=d, hostname="acme.com")
    ok = execute(queue(host).pk, scan_fn=lambda h, p: scanner.CertInfo(**{k: v for k, v in info().items()}))
    assert ok.status == "completed" and ok.result_status == "pass"
    host.refresh_from_db()
    assert host.latest_scan_id == ok.id

    def boom(h, p):
        raise scanner.ScanBlocked("acme.com resolves only to non-public addresses")

    bad = execute(queue(host).pk, scan_fn=boom)
    assert bad.status == "failed" and bad.result_status == "error" and "non-public" in bad.error


def test_add_host_scope_and_permissions(
    verified_domain, client_for, make_user, django_capture_on_commit_callbacks, monkeypatch
):
    owner, org, d = verified_domain
    from apps.ssl_monitor import tasks

    monkeypatch.setattr(tasks.scan_tls_host, "delay", lambda *a, **k: None)
    c = client_for(owner)
    url = f"/api/v1/domains/{d.id}/tls-hosts/"
    assert c.post(url, {"hostname": "evil.net"}, format="json").status_code == 400
    assert c.post(url, {"hostname": "acme.com.evil.net"}, format="json").status_code == 400
    r = c.post(url, {"hostname": "Mail.ACME.com", "port": 8443}, format="json")
    assert r.status_code == 201 and r.data["label"] == "mail.acme.com:8443"
    assert c.post(url, {"hostname": "mail.acme.com", "port": 8443}, format="json").status_code == 400  # duplicate
    host = MonitoredHost.objects.get(hostname="mail.acme.com")
    assert SslScan.objects.filter(host=host, status="queued").count() == 1
    # outsiders see nothing
    outsider = client_for(make_user("x@example.com"))
    assert outsider.get(url).status_code == 404
    assert outsider.post(f"/api/v1/tls-hosts/{host.id}/scan/").status_code == 404
    assert outsider.delete(f"/api/v1/tls-hosts/{host.id}/").status_code == 404
    assert outsider.get(f"/api/v1/organizations/{org.id}/certificates/").status_code == 404
    # a check is already queued
    assert c.post(f"/api/v1/tls-hosts/{host.id}/scan/").status_code == 400


def test_unverified_domain_cannot_add_hosts(make_user, make_org, client_for):
    owner = make_user()
    org = make_org(owner)
    d = Domain.objects.create(organization=org, name="acme.com")
    assert (
        client_for(owner)
        .post(f"/api/v1/domains/{d.id}/tls-hosts/", {"hostname": "acme.com"}, format="json")
        .status_code
        == 403
    )


def test_demo_certificates_and_summary(make_user, client_for):
    u = make_user()
    org = ensure_demo_workspace(u)
    data = client_for(u).get(f"/api/v1/organizations/{org.id}/certificates/").data
    s = data["summary"]
    assert s["total"] == 11 and s["expired"] == 2 and s["within_7"] == 2 and s["within_30"] == 2
    assert sum(m["count"] for m in s["by_month"]) == 11  # this month includes the ones that already expired in it
    names = {(c["hostname"], c["status"]) for c in data["certificates"]}
    assert ("www.brightpath-law.example", "fail") in names
    host = MonitoredHost.objects.filter(domain__organization=org).first()
    assert client_for(u).post(f"/api/v1/tls-hosts/{host.id}/scan/").status_code == 403  # read-only
    ov = client_for(u).get(f"/api/v1/organizations/{org.id}/overview/").data
    assert ov["tls"]["expired"] == 2 and ov["tls"]["soonest"][0]["days_left"] < 0


def test_summary_buckets_by_month():
    rows = [
        {"status": "pass", "days_left": 40, "not_after": (timezone.now() + timedelta(days=40)).isoformat()},
        {"status": None, "days_left": None, "not_after": None},
    ]
    s = summarize(rows)
    assert s["total"] == 2 and s["checked"] == 1 and s["healthy"] == 1 and len(s["by_month"]) == 12


def test_verified_domain_without_hosts_is_bootstrapped(verified_domain, client_for, monkeypatch):
    owner, org, d = verified_domain
    from apps.ssl_monitor import tasks

    monkeypatch.setattr(tasks.scan_tls_host, "delay", lambda *a, **k: None)
    rows = client_for(owner).get(f"/api/v1/organizations/{org.id}/certificates/").data["certificates"]
    assert {r["hostname"] for r in rows} == {"acme.com", "www.acme.com"} and all(r["pending"] for r in rows)
    # idempotent
    client_for(owner).get(f"/api/v1/domains/{d.id}/tls-hosts/")
    assert MonitoredHost.objects.filter(domain=d).count() == 2 and SslScan.objects.filter(host__domain=d).count() == 2
