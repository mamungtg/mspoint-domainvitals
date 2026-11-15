import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.alerts import notify
from apps.alerts.engine import evaluate_dmarc, evaluate_scan, sync
from apps.alerts.models import Alert, Channel, Delivery
from apps.dmarc.services import ingest_bytes
from apps.dns_monitor.models import DnsScan
from apps.dns_monitor.resolver import FakeResolver
from apps.dns_monitor.services import execute_scan
from apps.domains.models import Domain
from apps.organizations.models import Membership, Organization, Role
from apps.ssl_monitor.evaluate import evaluate
from apps.ssl_monitor.models import MonitoredHost
from apps.ssl_monitor.services import queue, store_result

from .test_dmarc import report_xml
from .test_dns_monitoring import zone
from .test_ssl import info

pytestmark = pytest.mark.django_db


@pytest.fixture
def org(make_user, make_org):
    owner = make_user("owner@acme.com")
    return make_org(owner)


@pytest.fixture
def domain(org):
    return Domain.objects.create(organization=org, name="acme.com", verified_at=timezone.now())


@pytest.fixture
def posts(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "http_post", lambda url, body, headers: sent.append((url, json.loads(body), headers)))
    return sent


def scan_with(domain, **statuses):
    results = {
        c: {"status": s, "findings": [{"severity": "critical", "title": f"{c} broken", "fix": "fix it"}]}
        for c, s in statuses.items()
    }
    return DnsScan.objects.create(domain=domain, status="completed", created_at=timezone.now(), results=results)


def test_new_workspace_gets_default_email_channel(org, make_user):
    ch = Channel.objects.get(organization=org)
    assert (
        ch.type == "email"
        and ch.notify_managers
        and set(ch.events) == {"check", "certificate", "dns_change", "dmarc_sender"}
    )
    demo = Organization.objects.create(name="Demo", owner=org.owner, is_demo=True)
    assert not Channel.objects.filter(organization=demo).exists()


def test_check_alert_lifecycle(domain, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_scan(scan_with(domain, dmarc="warn"))
    a = Alert.objects.get(status="open")
    assert a.severity == "warning" and a.title == "DMARC needs attention on acme.com" and "fix it" in a.detail
    assert [m.to for m in mail.outbox] == [["owner@acme.com"]] and mail.outbox[0].alternatives

    with django_capture_on_commit_callbacks(execute=True):
        evaluate_scan(scan_with(domain, dmarc="warn"))  # unchanged: no new message
        evaluate_scan(scan_with(domain, dmarc="error"))  # lookup trouble: ignored
    assert len(mail.outbox) == 1 and Alert.objects.filter(status="open").count() == 1

    with django_capture_on_commit_callbacks(execute=True):
        evaluate_scan(scan_with(domain, dmarc="fail"))
    a.refresh_from_db()
    assert a.severity == "critical" and len(mail.outbox) == 2 and "Now critical" in mail.outbox[1].body

    with django_capture_on_commit_callbacks(execute=True):
        evaluate_scan(scan_with(domain, dmarc="pass"))
    a.refresh_from_db()
    assert a.status == "resolved" and a.resolved_at and mail.outbox[2].subject.startswith("[Resolved]")
    assert Delivery.objects.filter(status="sent").count() == 3


def test_real_scan_opens_alert_and_records_dns_change(domain, django_capture_on_commit_callbacks):
    def run(z):
        with django_capture_on_commit_callbacks(execute=True):
            execute_scan(DnsScan.objects.create(domain=domain, created_at=timezone.now()), FakeResolver(z))

    run(zone())
    assert Alert.objects.filter(kind="check", status="open", title__startswith="DMARC").exists()  # no DMARC record
    assert not Alert.objects.filter(kind="dns_change").exists()  # first scan is the baseline
    run(zone(**{"acme.com": {"A": ["203.0.113.9"]}}))
    n = Alert.objects.get(kind="dns_change")
    assert n.status == "notice" and "203.0.113.9" in n.detail


def test_certificate_expiry_escalates_and_resolves(domain, django_capture_on_commit_callbacks):
    host = MonitoredHost.objects.create(domain=domain, hostname="acme.com")
    now = timezone.now()

    def check(days):
        i = info(not_after=(now + timedelta(days=days, hours=1)).isoformat())
        with django_capture_on_commit_callbacks(execute=True):
            store_result(queue(host, "scheduled"), i, evaluate(i, now))

    check(20)
    a = Alert.objects.get(kind="certificate")
    assert a.severity == "warning" and "20 days" in a.title
    check(5)
    a.refresh_from_db()
    assert a.severity == "critical" and "5 days" in a.title
    check(90)
    a.refresh_from_db()
    assert a.status == "resolved"
    assert [d.event for d in Delivery.objects.order_by("created_at")] == ["opened", "escalated", "resolved"]


def test_new_dmarc_sender_notice(domain, django_capture_on_commit_callbacks):
    r1 = ingest_bytes(report_xml(report_id="1"))
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_dmarc([r1.reports[0].pk])
    n = Alert.objects.get(kind="dmarc_sender")
    assert "203.0.113.9" in n.detail and n.data["messages"] == 7
    begin = int((timezone.now() - timedelta(hours=1)).timestamp())
    r2 = ingest_bytes(report_xml(report_id="2", begin=begin))
    evaluate_dmarc([r2.reports[0].pk])
    assert Alert.objects.filter(kind="dmarc_sender").count() == 1  # same IP again: not new


def test_channel_filters(org, domain, posts, django_capture_on_commit_callbacks):
    Channel.objects.filter(organization=org).delete()
    Channel.objects.create(
        organization=org,
        type="slack",
        name="crit",
        url="https://hooks.slack.com/x",
        events=["check"],
        min_severity="critical",
    )
    Channel.objects.create(
        organization=org, type="webhook", name="dns", url="https://example.com/hook", events=["dns_change"]
    )
    with django_capture_on_commit_callbacks(execute=True):
        sync(org, domain, "check", "k1", "warning", "warn")
        sync(org, domain, "check", "k2", "critical", "crit")
    assert [p[1]["text"] for p in posts] == ["crit"]


def test_webhook_signature_and_payload(org, domain, posts):
    ch = Channel.objects.create(
        organization=org, type="webhook", name="ops", url="https://example.com/hook", events=["check"]
    )
    a = Alert.objects.create(organization=org, domain=domain, kind="check", key="k", severity="critical", title="T")
    notify.send(ch, a, "opened")
    url, body, headers = posts[0]
    raw = json.dumps(body, separators=(",", ":")).encode()
    assert (
        headers["X-DomainVitals-Signature"] == "sha256=" + hmac.new(ch.secret.encode(), raw, hashlib.sha256).hexdigest()
    )
    assert (
        body["alert"]["domain"] == "acme.com" and body["event"] == "opened" and body["organization"]["name"] == org.name
    )


def test_teams_card(org, domain, posts):
    ch = Channel.objects.create(
        organization=org, type="teams", name="t", url="https://x.webhook.office.com/a", events=["check"]
    )
    a = Alert.objects.create(organization=org, domain=domain, kind="check", key="k", severity="warning", title="T")
    notify.send(ch, a, "resolved")
    card = posts[0][1]["attachments"][0]["content"]
    assert card["type"] == "AdaptiveCard" and card["body"][0]["text"] == "Resolved: T"


def test_ssrf_guard(monkeypatch):
    with pytest.raises(notify.DeliveryError, match="https"):
        notify.check_public_https("http://example.com/x")
    monkeypatch.setattr(notify.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.0.0.5", 443))])
    with pytest.raises(notify.DeliveryError, match="public"):
        notify.check_public_https("https://internal.example.com/x")


def test_failed_delivery_is_recorded(org, domain, monkeypatch):
    def boom(*a):
        raise notify.DeliveryError("The endpoint answered HTTP 500.")

    monkeypatch.setattr(notify, "http_post", boom)
    ch = Channel.objects.create(
        organization=org, type="slack", name="s", url="https://hooks.slack.com/x", events=["check"]
    )
    d = notify.deliver_now(Delivery.objects.create(channel=ch, event="test"))
    ch.refresh_from_db()
    assert d.status == "failed" and ch.last_error == "The endpoint answered HTTP 500."


# --- API -----------------------------------------------------------------------


def test_alert_api_and_acknowledge(org, domain, client_for, make_user):
    a = Alert.objects.create(organization=org, domain=domain, kind="check", key="k", severity="critical", title="T")
    viewer, member, outsider = make_user("v@acme.com"), make_user("m@acme.com"), make_user("x@other.com")
    Membership.objects.create(organization=org, user=viewer, role=Role.VIEWER)
    Membership.objects.create(organization=org, user=member, role=Role.MEMBER)
    r = client_for(viewer).get(f"/api/v1/organizations/{org.id}/alerts/")
    assert r.status_code == 200 and r.data["counts"] == {"open": 1, "critical": 1, "unacknowledged": 1}
    assert r.data["alerts"][0]["domain_name"] == "acme.com"
    assert client_for(viewer).post(f"/api/v1/alerts/{a.id}/acknowledge/").status_code == 403
    r = client_for(member).post(f"/api/v1/alerts/{a.id}/acknowledge/")
    assert r.status_code == 200 and r.data["acknowledged_by"] == "m@acme.com"
    assert client_for(outsider).get(f"/api/v1/organizations/{org.id}/alerts/").status_code == 404
    assert client_for(outsider).post(f"/api/v1/alerts/{a.id}/acknowledge/").status_code == 404


def test_channel_api(org, client_for, make_user, posts):
    owner = client_for(org.owner)
    url = f"/api/v1/organizations/{org.id}/alert-channels/"
    bad = owner.post(
        url, {"type": "slack", "name": "s", "url": "https://evil.example.com/x", "events": ["check"]}, format="json"
    )
    assert bad.status_code == 400
    r = owner.post(
        url,
        {
            "type": "slack",
            "name": "Ops",
            "url": "https://hooks.slack.com/services/A/B/C",
            "events": ["check", "certificate"],
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    cid = r.data["id"]
    r = owner.post(f"/api/v1/alert-channels/{cid}/test/")
    assert r.data == {"sent": True, "error": ""} and posts[0][1]["text"] == "Test notification from DomainVitals"
    r = owner.patch(f"/api/v1/alert-channels/{cid}/", {"enabled": False}, format="json")
    assert r.status_code == 200 and r.data["enabled"] is False
    r = owner.post(
        url,
        {"type": "email", "name": "Client", "recipients": ["IT@client.com", "nope"], "events": ["check"]},
        format="json",
    )
    assert r.status_code == 400
    r = owner.post(
        url, {"type": "email", "name": "Client", "recipients": ["IT@client.com"], "events": ["check"]}, format="json"
    )
    assert r.status_code == 201 and r.data["recipients"] == ["it@client.com"]

    member = make_user("m@acme.com")
    Membership.objects.create(organization=org, user=member, role=Role.MEMBER)
    mc = client_for(member)
    assert all(c["secret"] is None for c in mc.get(url).data)
    assert (
        mc.post(
            url, {"type": "email", "name": "x", "notify_managers": True, "events": ["check"]}, format="json"
        ).status_code
        == 403
    )
    assert mc.delete(f"/api/v1/alert-channels/{cid}/").status_code == 403
    assert owner.delete(f"/api/v1/alert-channels/{cid}/").status_code == 204


def test_demo_workspace_has_sample_alerts(make_user, client_for):
    c = client_for(make_user("demo@x.com"))
    org_id = c.post("/api/v1/organizations/demo/").data["id"]
    r = c.get(f"/api/v1/organizations/{org_id}/alerts/")
    assert r.data["counts"]["open"] == 6 and r.data["counts"]["critical"] == 5
    assert len(c.get(f"/api/v1/organizations/{org_id}/alerts/?status=notice").data["alerts"]) == 2
    assert len(c.get(f"/api/v1/organizations/{org_id}/alerts/?status=resolved").data["alerts"]) == 1


def test_demo_alerts_are_seeded_once_a_day(make_user, client_for):
    c = client_for(make_user("demo2@x.com"))
    org_id = c.post("/api/v1/organizations/demo/").data["id"]
    first = {a["id"] for a in c.get(f"/api/v1/organizations/{org_id}/alerts/").data["alerts"]}
    second = {a["id"] for a in c.get(f"/api/v1/organizations/{org_id}/alerts/").data["alerts"]}
    assert first == second
