"""Tenant scoping. Every organization-owned query goes through these helpers.

Rule: a non-member gets 404 (never 403) so object existence is not leaked.
"""

from django.http import Http404
from rest_framework.permissions import BasePermission

from .models import MANAGER_ROLES, Membership, Organization


def organizations_for(user):
    return Organization.objects.filter(memberships__user=user, status=Organization.Status.ACTIVE)


def get_membership_or_404(user, organization_id) -> Membership:
    m = (
        Membership.objects.select_related("organization")
        .filter(
            user=user,
            organization_id=organization_id,
            organization__status=Organization.Status.ACTIVE,
        )
        .first()
    )
    if m is None:
        raise Http404
    return m


class IsOrgManager(BasePermission):
    """Requires request.membership (set by the view) to be owner or admin."""

    message = "Only workspace owners and admins can do this."

    def has_permission(self, request, view):
        m = getattr(request, "membership", None)
        return m is not None and m.role in MANAGER_ROLES
