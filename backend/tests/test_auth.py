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


def test_register_logs_in_and_sends_verification(django_capture_on_commit_callbacks):
    c = csrf_client()
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post("/api/v1/auth/register/", {"email": "New@Example.com", "password": PASSWORD}, format="json")
    assert r.status_code == 201, r.data
    assert r.data["email"] == "new@example.com"
    assert r.data["email_verified"] is False
    assert c.get("/api/v1/auth/me/").status_code == 200
    assert len(mail.outbox) == 1
    token = re.search(r"token=(\S+)", mail.outbox[0].body).group(1)

    # login() rotates the CSRF token; a SPA re-reads the cookie before each write.
    c.credentials(HTTP_X_CSRFTOKEN=c.cookies["dv_csrftoken"].value)
    r = c.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
    assert r.status_code == 200
    assert User.objects.get(email="new@example.com").email_verified


def test_register_rejects_weak_password_and_duplicates(make_user):
    make_user("taken@example.com")
    c = csrf_client()
    assert (
        c.post("/api/v1/auth/register/", {"email": "a@example.com", "password": "123"}, format="json").status_code
        == 400
    )
    r = c.post("/api/v1/auth/register/", {"email": "TAKEN@example.com", "password": PASSWORD}, format="json")
    assert r.status_code == 400
    assert r.data["error"]["code"] == "validation_error"


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


def test_me_requires_auth():
    r = APIClient().get("/api/v1/auth/me/")
    assert r.status_code == 403
    assert r.data["error"]["code"] == "not_authenticated"


def test_health_is_public():
    r = APIClient().get("/api/v1/health/")
    assert r.status_code == 200
    assert r.data["checks"]["database"] == "ok"
    assert r["X-Request-ID"]
