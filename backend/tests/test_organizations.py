import pytest
from django.core import mail

from apps.organizations.models import Invitation, Membership, Role

pytestmark = pytest.mark.django_db


def test_create_and_list_only_own_workspaces(make_user, client_for, make_org):
    alice, bob = make_user("alice@example.com"), make_user("bob@example.com")
    make_org(bob, "Bob Co")
    c = client_for(alice)
    r = c.post("/api/v1/organizations/", {"name": "Alice Agency", "timezone": "Asia/Dhaka"}, format="json")
    assert r.status_code == 201
    assert r.data["role"] == "owner"
    names = [o["name"] for o in c.get("/api/v1/organizations/").data]
    assert names == ["Alice Agency"]


def test_invalid_timezone_rejected(make_user, client_for):
    r = client_for(make_user()).post("/api/v1/organizations/", {"name": "X", "timezone": "Mars/Base"}, format="json")
    assert r.status_code == 400


class TestTenantIsolation:
    """A user must never read or change another tenant's data. Outsiders get 404."""

    def test_outsider_gets_404_everywhere(self, make_user, client_for, make_org):
        owner, outsider = make_user("owner@example.com"), make_user("evil@example.com")
        org = make_org(owner)
        m = Membership.objects.get(organization=org, user=owner)
        inv, _ = Invitation.issue(organization=org, email="x@example.com", role=Role.MEMBER, invited_by=owner)
        c = client_for(outsider)
        assert c.get(f"/api/v1/organizations/{org.id}/").status_code == 404
        assert c.patch(f"/api/v1/organizations/{org.id}/", {"name": "pwned"}, format="json").status_code == 404
        assert c.get(f"/api/v1/organizations/{org.id}/members/").status_code == 404
        assert (
            c.post(f"/api/v1/organizations/{org.id}/members/", {"email": "e@x.com"}, format="json").status_code == 404
        )
        assert c.get(f"/api/v1/organizations/{org.id}/invitations/").status_code == 404
        assert c.patch(f"/api/v1/memberships/{m.id}/", {"role": "viewer"}, format="json").status_code == 404
        assert c.delete(f"/api/v1/memberships/{m.id}/").status_code == 404
        assert c.delete(f"/api/v1/invitations/{inv.id}/").status_code == 404
        org.refresh_from_db()
        assert org.name == "Acme Agency"

    def test_anonymous_blocked(self, client_for, make_user, make_org):
        org = make_org(make_user())
        assert client_for().get(f"/api/v1/organizations/{org.id}/").status_code == 403


def test_invite_and_accept(make_user, client_for, make_org, django_capture_on_commit_callbacks):
    owner = make_user("owner@example.com")
    org = make_org(owner)
    with django_capture_on_commit_callbacks(execute=True):
        r = client_for(owner).post(
            f"/api/v1/organizations/{org.id}/members/", {"email": "New@Example.com", "role": "admin"}, format="json"
        )
    assert r.status_code == 201
    token = mail.outbox[0].body.split("token=")[1].split()[0]

    # duplicate open invite rejected
    dup = client_for(owner).post(
        f"/api/v1/organizations/{org.id}/members/", {"email": "new@example.com"}, format="json"
    )
    assert dup.status_code == 400

    # wrong account cannot use the token
    other = make_user("other@example.com")
    assert client_for(other).post("/api/v1/invitations/accept/", {"token": token}, format="json").status_code == 400

    invitee = make_user("new@example.com")
    r = client_for(invitee).post("/api/v1/invitations/accept/", {"token": token}, format="json")
    assert r.status_code == 200
    assert Membership.objects.get(organization=org, user=invitee).role == "admin"
    # single use
    assert client_for(invitee).post("/api/v1/invitations/accept/", {"token": token}, format="json").status_code == 400


def test_unverified_user_cannot_accept(make_user, make_org, client_for):
    owner = make_user("owner@example.com")
    org = make_org(owner)
    _, raw = Invitation.issue(organization=org, email="u@example.com", role=Role.MEMBER, invited_by=owner)
    r = client_for(make_user("u@example.com", verified=False)).post(
        "/api/v1/invitations/accept/", {"token": raw}, format="json"
    )
    assert r.status_code == 403


class TestRoleRules:
    def _setup(self, make_user, make_org):
        owner = make_user("owner@example.com")
        org = make_org(owner)
        users = {}
        for role in ("admin", "member", "viewer"):
            u = make_user(f"{role}@example.com")
            users[role] = Membership.objects.create(organization=org, user=u, role=role)
        users["owner"] = Membership.objects.get(organization=org, user=owner)
        return org, users

    def test_member_cannot_manage(self, make_user, make_org, client_for):
        org, m = self._setup(make_user, make_org)
        c = client_for(m["member"].user)
        assert c.get(f"/api/v1/organizations/{org.id}/members/").status_code == 200
        assert (
            c.post(f"/api/v1/organizations/{org.id}/members/", {"email": "z@x.com"}, format="json").status_code == 403
        )
        assert c.patch(f"/api/v1/memberships/{m['viewer'].id}/", {"role": "admin"}, format="json").status_code == 403
        assert c.patch(f"/api/v1/organizations/{org.id}/", {"name": "x"}, format="json").status_code == 403

    def test_admin_cannot_touch_owner_or_escalate(self, make_user, make_org, client_for):
        org, m = self._setup(make_user, make_org)
        c = client_for(m["admin"].user)
        assert c.patch(f"/api/v1/memberships/{m['owner'].id}/", {"role": "viewer"}, format="json").status_code == 403
        assert c.patch(f"/api/v1/memberships/{m['member'].id}/", {"role": "owner"}, format="json").status_code == 403
        assert c.delete(f"/api/v1/memberships/{m['owner'].id}/").status_code == 403
        assert (
            c.post(
                f"/api/v1/organizations/{org.id}/members/", {"email": "o@x.com", "role": "owner"}, format="json"
            ).status_code
            == 403
        )
        assert c.patch(f"/api/v1/memberships/{m['member'].id}/", {"role": "viewer"}, format="json").status_code == 200

    def test_last_owner_protected(self, make_user, make_org, client_for):
        org, m = self._setup(make_user, make_org)
        c = client_for(m["owner"].user)
        assert c.patch(f"/api/v1/memberships/{m['owner'].id}/", {"role": "admin"}, format="json").status_code == 400
        assert c.delete(f"/api/v1/memberships/{m['owner'].id}/").status_code == 400
        # promote another owner, then demotion is allowed
        assert c.patch(f"/api/v1/memberships/{m['admin'].id}/", {"role": "owner"}, format="json").status_code == 200
        assert c.patch(f"/api/v1/memberships/{m['owner'].id}/", {"role": "admin"}, format="json").status_code == 200

    def test_member_can_leave(self, make_user, make_org, client_for):
        org, m = self._setup(make_user, make_org)
        assert client_for(m["viewer"].user).delete(f"/api/v1/memberships/{m['viewer'].id}/").status_code == 204
