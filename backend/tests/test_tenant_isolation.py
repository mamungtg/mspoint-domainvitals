"""Every API route that takes an object ID must refuse users from other
workspaces. This walks the URL conf, so new endpoints are covered automatically:
add a factory to OBJECTS when a route uses a new kind of ID."""

import uuid

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.alerts.models import Alert, Channel
from apps.dns_monitor.models import DnsScan
from apps.domains.models import Domain
from apps.organizations.models import Invitation, Membership, Role
from apps.ssl_monitor.models import MonitoredHost, SslScan

pytestmark = pytest.mark.django_db
METHODS = ["get", "post", "put", "patch", "delete"]
ALLOWED = {401, 403, 404, 405}


def walk(resolver, prefix=""):
    for p in resolver.url_patterns:
        if isinstance(p, URLResolver):
            yield from walk(p, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


@pytest.fixture
def victim(make_user, make_org):
    owner = make_user("victim@corp.com")
    org = make_org(owner)
    domain = Domain.objects.create(organization=org, name="corp.com", verified_at=timezone.now())
    scan = DnsScan.objects.create(domain=domain, status="completed", created_at=timezone.now())
    host = MonitoredHost.objects.create(domain=domain, hostname="corp.com")
    ssl_scan = SslScan.objects.create(host=host, created_at=timezone.now())
    member = make_user("colleague@corp.com")
    membership = Membership.objects.create(organization=org, user=member, role=Role.MEMBER)
    inv, _ = Invitation.issue(organization=org, email="new@corp.com", role=Role.MEMBER, invited_by=owner)
    alert = Alert.objects.create(organization=org, domain=domain, kind="check", key="k", severity="critical", title="t")
    channel = Channel.objects.filter(organization=org).first()
    return {
        "org_id": org.pk,
        "domain_id": domain.pk,
        "scan_id": scan.pk,
        "host_id": host.pk,
        "ssl_scan_id": ssl_scan.pk,
        "membership_id": membership.pk,
        "invitation_id": inv.pk,
        "alert_id": alert.pk,
        "channel_id": channel.pk,
    }


def test_other_workspaces_cannot_reach_any_object(victim, make_user, make_org, client_for, monkeypatch):
    monkeypatch.setattr(
        ScopedRateThrottle, "THROTTLE_RATES", {k: "100000/min" for k in ScopedRateThrottle.THROTTLE_RATES}
    )
    attacker = make_user("attacker@evil.com")
    make_org(attacker)  # owner of their own workspace, so every role check passes for *their* data
    c = client_for(attacker)
    checked, problems = 0, []
    for route, pattern in walk(get_resolver()):
        if not route.startswith("api/v1/") or not pattern.pattern.converters:
            continue
        kwargs = {}
        for name in pattern.pattern.converters:
            if name not in victim:
                problems.append(f"{route}: no test object for <{name}>; add it to the victim fixture")
                break
            kwargs[name] = victim[name]
        else:
            path = "/" + route
            for name, value in kwargs.items():
                path = path.replace(f"<uuid:{name}>", str(value))
            for m in METHODS:
                r = getattr(c, m)(path, {}, format="json")
                checked += 1
                if r.status_code not in ALLOWED:
                    problems.append(f"{m.upper()} {route} -> {r.status_code}")
    assert checked > 50, checked
    assert not problems, "\n".join(problems)


def test_random_ids_are_not_found(client_for, make_user, make_org):
    u = make_user("a@a.com")
    make_org(u)
    c = client_for(u)
    assert c.get(f"/api/v1/domains/{uuid.uuid4()}/").status_code == 404
    assert c.get(f"/api/v1/organizations/{uuid.uuid4()}/domains/").status_code == 404


def test_api_schema_is_not_public(client_for, make_user):
    from rest_framework.test import APIClient

    assert APIClient().get("/api/v1/schema/").status_code in (401, 403)
    assert client_for(make_user("u@x.com")).get("/api/v1/schema/").status_code == 403
    staff = make_user("staff@x.com")
    staff.is_staff = True
    staff.save()
    assert client_for(staff).get("/api/v1/schema/").status_code == 200
