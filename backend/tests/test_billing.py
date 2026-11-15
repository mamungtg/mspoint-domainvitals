import hashlib
import hmac
import json
import time
from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from apps.billing import stripe_api
from apps.billing.models import BillingAccount, StripeEvent
from apps.billing.plans import parse_lookup_key
from apps.dns_monitor.models import DnsScan
from apps.dns_monitor.tasks import schedule_due_scans
from apps.domains.models import Domain
from apps.organizations.models import Membership, Organization, Role

pytestmark = pytest.mark.django_db
SECRET = "whsec_test_secret"


@pytest.fixture
def org(make_user, make_org):
    return make_org(make_user("owner@acme.com"))


def set_plan(org, plan, status="active"):
    BillingAccount.objects.filter(organization=org).update(plan=plan, status=status, trial_ends_at=None)


def signed(client, event, secret=SECRET):
    body = json.dumps(event)
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/billing/stripe/webhook/",
        body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={t},v1={sig}",
    )


def sub(org, status="active", key="dv_msp_yearly", sub_id="sub_1", **kw):
    return {
        "id": sub_id,
        "object": "subscription",
        "customer": "cus_1",
        "status": status,
        "metadata": {"org_id": str(org.pk)},
        "cancel_at_period_end": False,
        "current_period_end": int(time.time()) + 86400 * 30,
        "items": {"data": [{"price": {"lookup_key": key}}]},
        **kw,
    }


def test_new_workspace_starts_agency_trial(org):
    acc = org.billing
    assert acc.status == "trialing" and acc.effective_plan == "agency" and acc.limits()["domains"] == 25
    acc.trial_ends_at = timezone.now() - timedelta(minutes=1)
    acc.save()
    assert acc.effective_plan == "free" and acc.limits()["domains"] == 1
    demo = Organization.objects.create(name="Demo", owner=org.owner, is_demo=True)
    assert not BillingAccount.objects.filter(organization=demo).exists()


def test_parse_lookup_key():
    assert parse_lookup_key("dv_agency_monthly") == ("agency", "month")
    assert parse_lookup_key("dv_msp_yearly") == ("msp", "year")
    assert parse_lookup_key("dv_enterprise_monthly") is None and parse_lookup_key("other") is None


def test_domain_limit(org, client_for):
    set_plan(org, "free", "free")
    c = client_for(org.owner)
    url = f"/api/v1/organizations/{org.id}/domains/"
    assert c.post(url, {"name": "one.com"}, format="json").status_code == 201
    r = c.post(url, {"name": "two.com"}, format="json")
    assert (
        r.status_code == 403
        and r.data["error"]["code"] == "plan_limit"
        and "Free plan includes 1 domain" in r.data["error"]["message"]
    )


def test_member_limit_counts_pending_invitations(org, client_for):
    set_plan(org, "starter")  # 3 members
    c = client_for(org.owner)
    url = f"/api/v1/organizations/{org.id}/members/"
    assert c.post(url, {"email": "a@acme.com", "role": "member"}, format="json").status_code == 201
    assert c.post(url, {"email": "b@acme.com", "role": "member"}, format="json").status_code == 201
    r = c.post(url, {"email": "c@acme.com", "role": "member"}, format="json")
    assert r.status_code == 403 and r.data["error"]["code"] == "plan_limit"


def test_channel_and_dmarc_gates(org, client_for):
    set_plan(org, "free", "free")
    c = client_for(org.owner)
    r = c.post(
        f"/api/v1/organizations/{org.id}/alert-channels/",
        {"type": "slack", "name": "s", "url": "https://hooks.slack.com/x", "events": ["check"]},
        format="json",
    )
    assert r.status_code == 403 and "not included in the Free plan" in r.data["error"]["message"]
    assert c.get(f"/api/v1/organizations/{org.id}/dmarc/?days=90").status_code == 403
    assert c.get(f"/api/v1/organizations/{org.id}/dmarc/?days=30").status_code == 200


def test_scheduler_skips_domains_over_the_limit(org):
    now = timezone.now()
    for i in range(3):
        Domain.objects.create(organization=org, name=f"d{i}.com", verified_at=now)
    set_plan(org, "free", "free")
    assert schedule_due_scans() == 1
    assert DnsScan.objects.get().domain.name == "d0.com"  # the oldest stays monitored


def test_billing_overview(org, client_for, make_user):
    member = make_user("m@acme.com")
    Membership.objects.create(organization=org, user=member, role=Role.MEMBER)
    r = client_for(org.owner).get(f"/api/v1/organizations/{org.id}/billing/")
    assert r.status_code == 200 and r.data["plan"] == "agency" and r.data["trial_active"] and r.data["can_manage"]
    assert r.data["usage"]["members"] == 2 and {p["key"] for p in r.data["plans"]} >= {
        "free",
        "starter",
        "agency",
        "msp",
    }
    assert client_for(member).get(f"/api/v1/organizations/{org.id}/billing/").data["can_manage"] is False
    orgs = client_for(org.owner).get("/api/v1/organizations/").data
    assert orgs[0]["billing"]["plan"] == "agency" and orgs[0]["billing"]["trial_ends_at"]


def test_checkout_and_portal(org, client_for, make_user, monkeypatch, settings):
    member = make_user("m@acme.com")
    Membership.objects.create(organization=org, user=member, role=Role.ADMIN)
    url = f"/api/v1/organizations/{org.id}/billing/checkout/"
    body = {"plan": "agency", "interval": "year"}
    assert client_for(member).post(url, body, format="json").status_code == 403  # owner only
    c = client_for(org.owner)
    settings.STRIPE_SECRET_KEY = ""
    r = c.post(url, body, format="json")
    assert r.status_code == 400 and "not set up" in str(r.data)
    calls = []
    monkeypatch.setattr(
        stripe_api,
        "checkout_url",
        lambda acc, plan, interval, email: calls.append((plan, interval, email)) or "https://checkout.stripe.com/c/x",
    )
    r = c.post(url, body, format="json")
    assert r.data == {"url": "https://checkout.stripe.com/c/x"} and calls == [("agency", "year", "owner@acme.com")]
    assert c.post(url, {"plan": "enterprise", "interval": "year"}, format="json").status_code == 400

    portal = f"/api/v1/organizations/{org.id}/billing/portal/"
    assert c.post(portal).status_code == 400  # no Stripe customer yet
    BillingAccount.objects.filter(organization=org).update(
        stripe_customer_id="cus_1", stripe_subscription_id="sub_1", status="active"
    )
    monkeypatch.setattr(stripe_api, "portal_url", lambda acc: "https://billing.stripe.com/p/x")
    assert c.post(portal).data == {"url": "https://billing.stripe.com/p/x"}
    assert c.post(url, body, format="json").status_code == 400  # already subscribed: use the portal


def test_webhook_signature_and_sync(org, client_for, settings, monkeypatch):
    c = client_for()
    settings.STRIPE_WEBHOOK_SECRET = ""
    assert signed(c, {"id": "evt_0", "type": "x", "data": {"object": {}}}).status_code == 503
    settings.STRIPE_WEBHOOK_SECRET = SECRET
    assert signed(c, {"id": "evt_0", "type": "x", "data": {"object": {}}}, secret="wrong").status_code == 400

    ev = {"id": "evt_1", "type": "customer.subscription.updated", "data": {"object": sub(org)}}
    assert signed(c, ev).status_code == 200
    acc = BillingAccount.objects.get(organization=org)
    assert (acc.plan, acc.interval, acc.status, acc.stripe_customer_id) == ("msp", "year", "active", "cus_1")
    assert acc.limits()["domains"] == 100 and acc.trial_ends_at is None
    assert signed(c, ev).status_code == 200 and StripeEvent.objects.count() == 1  # redelivery is ignored

    ev = {"id": "evt_2", "type": "customer.subscription.deleted", "data": {"object": sub(org, status="canceled")}}
    signed(c, ev)
    acc.refresh_from_db()
    assert acc.effective_plan == "free" and acc.status == "canceled"


def test_checkout_completed_and_payment_failed(org, client_for, settings, monkeypatch):
    settings.STRIPE_WEBHOOK_SECRET = SECRET
    c = client_for()
    monkeypatch.setattr(stripe_api, "retrieve_subscription", lambda sid: sub(org, key="dv_starter_monthly", sub_id=sid))
    signed(
        c,
        {
            "id": "evt_a",
            "type": "checkout.session.completed",
            "data": {"object": {"mode": "subscription", "subscription": "sub_9"}},
        },
    )
    acc = BillingAccount.objects.get(organization=org)
    assert (acc.plan, acc.stripe_subscription_id) == ("starter", "sub_9")

    monkeypatch.setattr(
        stripe_api,
        "retrieve_subscription",
        lambda sid: sub(org, status="past_due", key="dv_starter_monthly", sub_id=sid),
    )
    signed(c, {"id": "evt_b", "type": "invoice.payment_failed", "data": {"object": {"subscription": "sub_9"}}})
    acc.refresh_from_db()
    assert acc.status == "past_due" and acc.effective_plan == "starter"  # keeps the plan while Stripe retries
    assert mail.outbox[-1].to == ["owner@acme.com"] and "Payment failed" in mail.outbox[-1].subject


def test_set_plan_command(org):
    call_command("set_plan", str(org.pk), "enterprise", "--domains", "500")
    acc = BillingAccount.objects.get(organization=org)
    assert acc.effective_plan == "enterprise" and acc.limits()["domains"] == 500
