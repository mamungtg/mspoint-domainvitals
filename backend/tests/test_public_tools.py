import pytest
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.ssl_monitor import scanner
from apps.ssl_monitor import views as ssl_views

from .test_auth import csrf_client
from .test_domains import fake_dns  # noqa: F401 - fixture
from .test_ssl import info

pytestmark = pytest.mark.django_db
CHECK = "/api/v1/tools/check/"


@pytest.fixture
def tight_limits(monkeypatch):
    rates = dict(ScopedRateThrottle.THROTTLE_RATES, public_tools="2/hour", public_ssl="1/hour", tools="100/hour")
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", rates)


def test_anonymous_needs_csrf(fake_dns):  # noqa: F811
    assert (
        APIClient(enforce_csrf_checks=True)
        .post(CHECK, {"domain": "acme.com", "check": "spf"}, format="json")
        .status_code
        == 403
    )
    r = csrf_client().post(CHECK, {"domain": "acme.com", "check": "spf"}, format="json")
    assert r.status_code == 200 and r.data["summary"] == {"spf": "pass"}


def test_anonymous_limit_is_per_ip(fake_dns, tight_limits):  # noqa: F811
    c = csrf_client()
    ip_a = {"HTTP_X_FORWARDED_FOR": "198.51.100.1"}
    for _ in range(2):
        assert c.post(CHECK, {"domain": "acme.com", "check": "mx"}, format="json", **ip_a).status_code == 200
    assert c.post(CHECK, {"domain": "acme.com", "check": "mx"}, format="json", **ip_a).status_code == 429
    # another visitor is not affected
    assert (
        c.post(
            CHECK, {"domain": "acme.com", "check": "mx"}, format="json", HTTP_X_FORWARDED_FOR="198.51.100.2"
        ).status_code
        == 200
    )


def test_signed_in_users_use_the_member_limit(fake_dns, tight_limits, make_user, client_for):  # noqa: F811
    c = client_for(make_user())
    for _ in range(4):
        assert c.post(CHECK, {"domain": "acme.com", "check": "mx"}, format="json").status_code == 200


def test_public_propagation(monkeypatch):
    from apps.dns_monitor import views as dns_views

    monkeypatch.setattr(
        dns_views, "check_propagation", lambda name, rtype: {"name": name, "type": rtype, "servers": []}
    )
    r = csrf_client().post("/api/v1/tools/propagation/", {"name": "www.acme.com", "type": "A"}, format="json")
    assert r.status_code == 200 and r.data["name"] == "www.acme.com"


def test_public_ssl_check(monkeypatch, tight_limits):
    class Fake:
        def to_dict(self):
            return info()

    monkeypatch.setattr(ssl_views.scanner, "scan", lambda host, port: Fake())
    c = csrf_client()
    r = c.post(
        "/api/v1/tools/ssl/", {"hostname": "https://Acme.com/x"}, format="json", HTTP_X_FORWARDED_FOR="203.0.113.5"
    )
    assert r.status_code == 200, r.data
    assert (
        r.data["hostname"] == "acme.com"
        and r.data["days_left"] is not None
        and r.data["result"]["status"] in ("pass", "warn")
    )
    assert (
        c.post(
            "/api/v1/tools/ssl/", {"hostname": "acme.com"}, format="json", HTTP_X_FORWARDED_FOR="203.0.113.5"
        ).status_code
        == 429
    )

    def blocked(host, port):
        raise scanner.ScanBlocked("private")

    monkeypatch.setattr(ssl_views.scanner, "scan", blocked)
    r = c.post(
        "/api/v1/tools/ssl/", {"hostname": "intranet.acme.com"}, format="json", HTTP_X_FORWARDED_FOR="203.0.113.6"
    )
    assert r.status_code == 400 and "private address" in str(r.data)
    r = c.post(
        "/api/v1/tools/ssl/", {"hostname": "acme.com", "port": 22}, format="json", HTTP_X_FORWARDED_FOR="203.0.113.7"
    )
    assert r.status_code == 400
    r = c.post("/api/v1/tools/ssl/", {"hostname": "10.0.0.1"}, format="json", HTTP_X_FORWARDED_FOR="203.0.113.8")
    assert r.status_code == 400
