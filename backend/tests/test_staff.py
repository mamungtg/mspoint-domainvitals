from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.billing.models import BillingAccount
from apps.domains.models import Domain

pytestmark = pytest.mark.django_db
URLS = ["/api/v1/staff/overview/", "/api/v1/staff/workspaces/", "/api/v1/staff/users/"]


@pytest.fixture
def world(make_user, make_org):
    staff = make_user("ops@mspointit.com", is_staff=True)
    a = make_user("owner@agency.test", full_name="Ann Owner")
    b = make_user("other@msp.test")
    make_user("new@x.test", verified=False)
    org_a = make_org(a, "Agency A")
    org_b = make_org(b, "=HYPERLINK(evil)")
    Domain.objects.create(organization=org_a, name="agency-a.com", verified_at=timezone.now())
    BillingAccount.objects.update_or_create(
        organization=org_a,
        defaults={"plan": "agency", "status": "active", "interval": "month", "stripe_subscription_id": "sub_1"},
    )
    BillingAccount.objects.update_or_create(
        organization=org_b,
        defaults={"plan": "agency", "status": "trialing", "trial_ends_at": timezone.now() + timedelta(days=3)},
    )
    return {"staff": staff, "a": a, "org_a": org_a, "org_b": org_b}


def test_customers_cannot_open_the_staff_console(world, client_for):
    for url in [*URLS, f"/api/v1/staff/workspaces/{world['org_a'].pk}/"]:
        assert client_for(world["a"]).get(url).status_code == 403, url
        assert client_for().get(url).status_code in (401, 403), url


def test_overview_counts_customers_and_revenue(world, client_for):
    r = client_for(world["staff"]).get("/api/v1/staff/overview/")
    assert r.status_code == 200
    d = r.data
    assert d["workspaces"] == 2 and d["paying"] == 1 and d["trialing"] == 1
    assert d["mrr"] == 79 and d["paying_by_plan"] == {"agency": 1}
    assert d["users"] == 4 and d["users_unverified"] == 1
    assert [t["name"] for t in d["trials_ending_7d"]] == ["=HYPERLINK(evil)"]


def test_workspace_list_filters_and_detail(world, client_for):
    c = client_for(world["staff"])
    rows = c.get("/api/v1/staff/workspaces/").data["results"]
    assert {r["name"] for r in rows} == {"Agency A", "=HYPERLINK(evil)"}
    a = next(r for r in rows if r["name"] == "Agency A")
    assert a["owner"]["email"] == "owner@agency.test" and a["domains"] == 1 and a["billing"]["mrr"] == 79

    assert [r["name"] for r in c.get("/api/v1/staff/workspaces/?status=trialing").data["results"]] == [
        "=HYPERLINK(evil)"
    ]
    assert [r["name"] for r in c.get("/api/v1/staff/workspaces/?q=agency-a").data["results"]] == ["Agency A"]

    d = c.get(f"/api/v1/staff/workspaces/{world['org_a'].pk}/").data
    assert d["members"][0]["email"] == "owner@agency.test"
    assert d["domain_list"][0]["name"] == "agency-a.com"


def test_csv_export_escapes_formulas(world, client_for):
    r = client_for(world["staff"]).get("/api/v1/staff/workspaces/?export=csv")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
    body = r.content.decode()
    assert "'=HYPERLINK(evil)" in body and "\n=HYPERLINK" not in body
    users = client_for(world["staff"]).get("/api/v1/staff/users/?export=csv").content.decode()
    assert "owner@agency.test" in users and "Agency A (owner)" in users


def test_users_list_and_staff_command(world, client_for):
    rows = client_for(world["staff"]).get("/api/v1/staff/users/?verified=no").data["results"]
    assert [r["email"] for r in rows] == ["new@x.test"]
    call_command("staff", "owner@agency.test")
    world["a"].refresh_from_db()
    me = client_for(world["a"]).get("/api/v1/auth/me/").data
    assert me["is_staff"] is True
    assert client_for(world["a"]).get("/api/v1/staff/overview/").status_code == 200
    call_command("staff", "owner@agency.test", "--remove")
    world["a"].refresh_from_db()
    assert not world["a"].is_staff


def test_plans_set_by_hand_are_not_revenue(world, client_for, make_org):
    own = make_org(world["staff"], "MSPoint")
    call_command("set_plan", "MSPoint", "enterprise")
    c = client_for(world["staff"])
    d = c.get("/api/v1/staff/overview/").data
    assert d["paying"] == 1 and d["manual"] == 1 and d["mrr"] == 79 and d["paying_by_plan"] == {"agency": 1}
    rows = c.get("/api/v1/staff/workspaces/?status=manual").data["results"]
    assert [r["name"] for r in rows] == ["MSPoint"] and rows[0]["billing"]["status"] == "manual"
    assert [r["name"] for r in c.get("/api/v1/staff/workspaces/?status=active").data["results"]] == ["Agency A"]
    assert own.pk
