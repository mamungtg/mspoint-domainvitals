import pytest

from apps.dns_monitor.models import DnsScan
from apps.dns_monitor.resolver import FakeResolver
from apps.domains import views as domain_views
from apps.domains.demo import ensure_demo_workspace
from apps.domains.models import Domain
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db

ZONE = {
    "acme.com": {"TXT": ["v=spf1 ip4:192.0.2.1 -all"], "MX": [(10, "mx.acme.com")]},
    "mx.acme.com": {"A": ["192.0.2.25"]},
    "_dmarc.acme.com": {"TXT": ["v=DMARC1; p=reject; rua=mailto:d@acme.com"]},
}


@pytest.fixture
def fake_dns(monkeypatch):
    zone = dict(ZONE)

    def factory(*a, **k):
        return FakeResolver(zone)

    monkeypatch.setattr(domain_views, "LiveResolver", factory)
    monkeypatch.setattr("apps.dns_monitor.services.LiveResolver", factory)
    return zone


def add(client, org, name="https://ACME.com/"):
    return client.post(f"/api/v1/organizations/{org.id}/domains/", {"name": name}, format="json")


def test_add_normalises_and_lists(make_user, make_org, client_for):
    owner = make_user()
    org = make_org(owner)
    c = client_for(owner)
    r = add(c, org)
    assert r.status_code == 201 and r.data["name"] == "acme.com" and not r.data["is_verified"]
    assert r.data["verification"]["host"] == "_domainvitals.acme.com"
    assert add(c, org, "acme.com").status_code == 400  # duplicate
    assert add(c, org, "not a domain").status_code == 400
    assert [d["name"] for d in c.get(f"/api/v1/organizations/{org.id}/domains/").data] == ["acme.com"]


def test_unverified_email_cannot_add(make_user, make_org, client_for):
    u = make_user(verified=False)
    assert add(client_for(u), make_org(u)).status_code == 403


def test_viewer_cannot_write(make_user, make_org, client_for):
    owner, viewer = make_user("o@x.com"), make_user("v@x.com")
    org = make_org(owner)
    Membership.objects.create(organization=org, user=viewer, role="viewer")
    assert add(client_for(viewer), org).status_code == 403
    d = Domain.objects.create(organization=org, name="acme.com")
    assert client_for(viewer).get(f"/api/v1/domains/{d.id}/").status_code == 200
    assert client_for(viewer).delete(f"/api/v1/domains/{d.id}/").status_code == 403


def test_outsider_gets_404(make_user, make_org, client_for):
    org = make_org(make_user("o@x.com"))
    d = Domain.objects.create(organization=org, name="acme.com")
    scan = DnsScan.objects.create(domain=d, created_at=d.created_at)
    c = client_for(make_user("evil@x.com"))
    for method, url in [
        ("get", f"/api/v1/organizations/{org.id}/domains/"),
        ("get", f"/api/v1/organizations/{org.id}/overview/"),
        ("get", f"/api/v1/domains/{d.id}/"),
        ("patch", f"/api/v1/domains/{d.id}/"),
        ("delete", f"/api/v1/domains/{d.id}/"),
        ("post", f"/api/v1/domains/{d.id}/verify/"),
        ("post", f"/api/v1/domains/{d.id}/scan/"),
        ("get", f"/api/v1/domains/{d.id}/scans/"),
        ("get", f"/api/v1/scans/{scan.id}/"),
    ]:
        assert getattr(c, method)(url, {}, format="json").status_code == 404, url
    assert Domain.objects.filter(pk=d.pk).exists()


def test_verify_then_scan(make_user, make_org, client_for, fake_dns, django_capture_on_commit_callbacks):
    owner = make_user()
    org = make_org(owner)
    c = client_for(owner)
    d = add(c, org).data
    assert c.post(f"/api/v1/domains/{d['id']}/scan/").status_code == 403  # not verified yet
    r = c.post(f"/api/v1/domains/{d['id']}/verify/")
    assert r.status_code == 400  # record not published yet
    fake_dns["_domainvitals.acme.com"] = {"TXT": [d["verification"]["value"]]}
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(f"/api/v1/domains/{d['id']}/verify/")
    assert r.status_code == 200 and r.data["is_verified"]
    dom = c.get(f"/api/v1/domains/{d['id']}/").data
    assert dom["latest_scan"]["status"] == "completed" and dom["latest_scan"]["summary"]["spf"] == "pass"

    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(f"/api/v1/domains/{d['id']}/scan/")
    assert r.status_code == 202
    assert c.post(f"/api/v1/domains/{d['id']}/scan/").status_code == 429  # cooldown
    scans = c.get(f"/api/v1/domains/{d['id']}/scans/").data
    assert len(scans) == 2
    detail = c.get(f"/api/v1/scans/{scans[0]['id']}/").data
    assert set(detail["results"]) == {"spf", "dkim", "dmarc", "mx", "dns"}


def test_patch_selectors_validation(make_user, make_org, client_for):
    owner = make_user()
    org = make_org(owner)
    d = Domain.objects.create(organization=org, name="acme.com")
    c = client_for(owner)
    assert c.patch(f"/api/v1/domains/{d.id}/", {"dkim_selectors": ["Acme1", "acme1"]}, format="json").data[
        "dkim_selectors"
    ] == ["acme1"]
    assert c.patch(f"/api/v1/domains/{d.id}/", {"dkim_selectors": ["bad selector!"]}, format="json").status_code == 400


def test_demo_workspace_is_seeded_and_read_only(make_user, client_for):
    u = make_user()
    org = ensure_demo_workspace(u)
    assert ensure_demo_workspace(u).pk == org.pk  # idempotent
    c = client_for(u)
    ov = c.get(f"/api/v1/organizations/{org.id}/overview/").data
    assert ov["domains"] == {"total": 6, "verified": 5, "unverified": 1, "scanned": 5}
    assert ov["issues"]["critical"] > 0 and len([p for p in ov["score_trend"] if p["score"]]) == 14
    assert ov["dmarc_policies"]["missing"] == 1
    dom = Domain.objects.get(organization=org, name="atlas-fitness.example")
    assert c.post(f"/api/v1/domains/{dom.id}/scan/").status_code == 403
    assert add(c, org, "x.com").status_code == 403
    m = Membership.objects.get(organization=org, user=u)
    assert c.delete(f"/api/v1/memberships/{m.id}/").status_code == 204
    assert not Organization.objects.filter(pk=org.pk).exists()


def test_register_creates_demo_workspace(client_for):
    from tests.test_auth import csrf_client

    c = csrf_client()
    r = c.post("/api/v1/auth/register/", {"email": "n@x.com", "password": "Correct-Horse-Battery-9"}, format="json")
    assert r.status_code == 201
    c.credentials(HTTP_X_CSRFTOKEN=c.cookies["dv_csrftoken"].value)
    orgs = c.get("/api/v1/organizations/").data
    assert [o["is_demo"] for o in orgs] == [True]


def test_tools_check(make_user, client_for, fake_dns):
    c = client_for(make_user())
    r = c.post("/api/v1/tools/check/", {"domain": "acme.com", "check": "spf"}, format="json")
    assert r.status_code == 200 and r.data["summary"] == {"spf": "pass"}
    r = c.post("/api/v1/tools/check/", {"domain": "acme.com"}, format="json")
    assert set(r.data["summary"]) == {"spf", "dkim", "dmarc", "mx", "dns"}
    assert "records" not in r.data["results"]["dns"]["data"]
    r = c.post("/api/v1/tools/check/", {"domain": "acme.com", "check": "dns"}, format="json")
    assert r.status_code == 200 and set(r.data["summary"]) == {"dns"}
    assert "name_servers" in r.data["results"]["dns"]["data"] and "records" not in r.data["results"]["dns"]["data"]
    assert c.post("/api/v1/tools/check/", {"domain": "10.0.0.1"}, format="json").status_code == 400
