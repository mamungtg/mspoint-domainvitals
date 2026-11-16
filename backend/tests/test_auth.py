import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def csrf_client():
    c = APIClient(enforce_csrf_checks=True)
    c.get("/api/v1/auth/csrf/")
    c.credentials(HTTP_X_CSRFTOKEN=c.cookies["dv_csrftoken"].value)
    return c


def test_register_requires_confirmation_before_sign_in(django_capture_on_commit_callbacks):
    c = csrf_client()
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post("/api/v1/auth/register/", {"email": "New@Example.com", "password": PASSWORD}, format="json")
    assert r.status_code == 201, r.data
    assert r.data == {"email": "new@example.com", "verification_required": True}
    assert c.get("/api/v1/auth/me/").status_code == 403  # no session after sign-up
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.alternatives and "text/html" in msg.alternatives[0][1]
    token = re.search(r"token=(\S+)", msg.body).group(1)

    login = {"email": "new@example.com", "password": PASSWORD}
    r = c.post("/api/v1/auth/login/", login, format="json")
    assert r.status_code == 403 and r.data["error"]["code"] == "email_not_verified"

    r = c.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
    assert r.status_code == 200
    assert User.objects.get(email="new@example.com").email_verified
    assert c.post("/api/v1/auth/login/", login, format="json").status_code == 200


def test_wrong_password_does_not_reveal_unverified_account(make_user):
    make_user("u@example.com", verified=False)
    r = csrf_client().post("/api/v1/auth/login/", {"email": "u@example.com", "password": "wrong"}, format="json")
    assert r.data["error"]["message"] == "Invalid email or password."


def test_resend_verification_signed_out(make_user, django_capture_on_commit_callbacks):
    make_user("u@example.com", verified=False)
    make_user("ok@example.com")
    c = csrf_client()
    with django_capture_on_commit_callbacks(execute=True):
        for email in ("u@example.com", "ok@example.com", "nobody@example.com"):
            assert c.post("/api/v1/auth/verify-email/resend/", {"email": email}, format="json").status_code == 202
    assert [m.to for m in mail.outbox] == [["u@example.com"]]


def test_unverified_session_is_ignored(make_user):
    u = make_user("u@example.com", verified=False)
    c = APIClient()
    c.force_login(u)  # a session opened before verification became mandatory
    assert c.get("/api/v1/auth/me/").status_code == 403
    u.mark_email_verified()
    assert c.get("/api/v1/auth/me/").status_code == 200


def test_verify_user_command(make_user):
    from django.core.management import call_command

    make_user("u@example.com", verified=False)
    call_command("verify_user", "U@example.com")
    assert User.objects.get(email="u@example.com").email_verified


def test_register_rejects_weak_password_and_duplicates(make_user):
    make_user("taken@example.com")
    c = csrf_client()
    assert (
        c.post("/api/v1/auth/register/", {"email": "a@example.com", "password": "123"}, format="json").status_code
        == 400
    )
    r = c.post("/api/v1/auth/register/", {"email": "a@example.com", "password": "123"}, format="json")
    assert r.data["error"]["code"] == "validation_error"


def test_register_does_not_reveal_existing_accounts(make_user, django_capture_on_commit_callbacks):
    make_user("taken@example.com")
    make_user("pending@example.com", verified=False)
    c = csrf_client()
    with django_capture_on_commit_callbacks(execute=True):
        new = c.post("/api/v1/auth/register/", {"email": "fresh@example.com", "password": PASSWORD}, format="json")
        taken = c.post("/api/v1/auth/register/", {"email": "TAKEN@example.com", "password": PASSWORD}, format="json")
        pending = c.post(
            "/api/v1/auth/register/", {"email": "pending@example.com", "password": PASSWORD}, format="json"
        )
    assert new.status_code == taken.status_code == pending.status_code == 201
    assert set(taken.data) == set(new.data) and taken.data["verification_required"] is True
    subjects = {m.to[0]: m.subject for m in mail.outbox}
    assert subjects["taken@example.com"] == "You already have a DomainVitals account"
    assert "Confirm" in subjects["pending@example.com"] and "Confirm" in subjects["fresh@example.com"]
    assert User.objects.get(email="taken@example.com").check_password(PASSWORD)  # untouched


def test_account_lockout_after_repeated_failures(make_user, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", dict(ScopedRateThrottle.THROTTLE_RATES, login="1000/min"))
    make_user("a@example.com")
    c = csrf_client()
    for i in range(10):
        ip = f"198.51.100.{i}"  # spread over many addresses
        r = c.post(
            "/api/v1/auth/login/",
            {"email": "a@example.com", "password": "wrong"},
            format="json",
            HTTP_X_FORWARDED_FOR=ip,
        )
        assert r.status_code in (401, 403)
    r = c.post("/api/v1/auth/login/", {"email": "a@example.com", "password": PASSWORD}, format="json")
    assert r.status_code == 429 and "Too many failed attempts" in r.data["error"]["message"]
    from apps.accounts.lockout import clear_failed_logins

    clear_failed_logins("a@example.com")
    assert (
        c.post("/api/v1/auth/login/", {"email": "a@example.com", "password": PASSWORD}, format="json").status_code
        == 200
    )


def test_login_requires_csrf(make_user):
    make_user("a@example.com")
    c = APIClient(enforce_csrf_checks=True)
    r = c.post("/api/v1/auth/login/", {"email": "a@example.com", "password": PASSWORD}, format="json")
    assert r.status_code == 403


def test_login_success_and_failure(make_user):
    make_user("a@example.com")
    c = csrf_client()
    bad = c.post("/api/v1/auth/login/", {"email": "a@example.com", "password": "wrong"}, format="json")
    assert bad.status_code in (401, 403)
    assert "request_id" in bad.data
    ok = c.post("/api/v1/auth/login/", {"email": "A@example.com", "password": PASSWORD}, format="json")
    assert ok.status_code == 200
    assert AuditLog.objects.filter(action="user.logged_in").exists()


def test_tampered_verification_token_rejected(make_user):
    make_user("a@example.com", verified=False)
    r = csrf_client().post("/api/v1/auth/verify-email/", {"token": "garbage:abc"}, format="json")
    assert r.status_code == 400


def test_password_reset_flow_no_enumeration(make_user, django_capture_on_commit_callbacks):
    make_user("a@example.com")
    c = csrf_client()
    with django_capture_on_commit_callbacks(execute=True):
        assert c.post("/api/v1/auth/password-reset/", {"email": "nobody@example.com"}, format="json").status_code == 202
        assert c.post("/api/v1/auth/password-reset/", {"email": "a@example.com"}, format="json").status_code == 202
    assert len(mail.outbox) == 1
    uid = re.search(r"uid=([^&\s]+)", mail.outbox[0].body).group(1)
    token = re.search(r"token=(\S+)", mail.outbox[0].body).group(1)
    new = "Another-Strong-Pass-42"
    r = c.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": new}, format="json")
    assert r.status_code == 204
    # token is single use
    r = c.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": new}, format="json")
    assert r.status_code == 400
    assert User.objects.get(email="a@example.com").check_password(new)


def test_password_reset_confirms_email(make_user, django_capture_on_commit_callbacks):
    make_user("a@example.com", verified=False)
    c = csrf_client()
    with django_capture_on_commit_callbacks(execute=True):
        c.post("/api/v1/auth/password-reset/", {"email": "a@example.com"}, format="json")
    uid = re.search(r"uid=([^&\s]+)", mail.outbox[0].body).group(1)
    token = re.search(r"token=(\S+)", mail.outbox[0].body).group(1)
    r = c.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "Another-Strong-Pass-42"},
        format="json",
    )
    assert r.status_code == 204 and User.objects.get(email="a@example.com").email_verified


def test_me_requires_auth():
    r = APIClient().get("/api/v1/auth/me/")
    assert r.status_code == 403
    assert r.data["error"]["code"] == "not_authenticated"


def test_health_is_public():
    r = APIClient().get("/api/v1/health/")
    assert r.status_code == 200
    assert r.data["checks"]["database"] == "ok"
    assert r["X-Request-ID"]
