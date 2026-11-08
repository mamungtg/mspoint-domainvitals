import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization, Role

PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture
def make_user(db):
    def _make(email="user@example.com", verified=True, **kw):
        return User.objects.create_user(email=email, password=PASSWORD, email_verified=verified, **kw)

    return _make


@pytest.fixture
def client_for():
    def _client(user=None):
        c = APIClient()
        if user is not None:
            c.force_authenticate(user)
        return c

    return _client


@pytest.fixture
def make_org(db):
    def _make(owner, name="Acme Agency"):
        org = Organization.objects.create(name=name, owner=owner)
        Membership.objects.create(organization=org, user=owner, role=Role.OWNER)
        return org

    return _make
