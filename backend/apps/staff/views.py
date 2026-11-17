"""Staff console: every customer, workspace and subscription in one place.

Read-only and staff-only (User.is_staff). Grant access with
`manage.py staff <email>`.
"""

from __future__ import annotations

import csv
from datetime import timedelta

from django.db.models import Count, Max, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.billing.models import BillingAccount
from apps.billing.plans import PLANS
from apps.domains.models import Domain
from apps.organizations.models import Membership, Organization


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


PERMS = [IsAuthenticated, IsStaff]
PAID = (BillingAccount.Status.ACTIVE, BillingAccount.Status.PAST_DUE)


def _manual(b: BillingAccount | None) -> bool:
    """Plan given by hand (set_plan: own workspace, Enterprise contract, comp), not a Stripe subscription."""
    return bool(b and b.status in PAID and not b.stripe_subscription_id)


def _monthly_value(b: BillingAccount | None) -> float:
    """Recurring revenue per month of a paying Stripe subscription (yearly / 12)."""
    if not b or b.status not in PAID or _manual(b):
        return 0.0
    price = (PLANS.get(b.plan) or {}).get("price")
    if not price:
        return 0.0
    return price["year"] / 12 if b.interval == "year" else float(price["month"])


def _billing(b: BillingAccount | None) -> dict:
    if not b:
        return {
            "plan": "free",
            "effective_plan": "free",
            "status": "free",
            "interval": "",
            "trial_ends_at": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
            "stripe_customer_id": "",
            "mrr": 0,
        }
    return {
        "plan": b.plan,
        "effective_plan": b.effective_plan,
        "status": "manual"
        if _manual(b)
        else ("trial_ended" if b.status == BillingAccount.Status.TRIALING and not b.trial_active else b.status),
        "interval": b.interval,
        "trial_ends_at": b.trial_ends_at,
        "current_period_end": b.current_period_end,
        "cancel_at_period_end": b.cancel_at_period_end,
        "stripe_customer_id": b.stripe_customer_id,
        "mrr": round(_monthly_value(b), 2),
    }


def _workspaces(params):
    qs = (
        Organization.objects.filter(is_demo=False)
        .select_related("owner", "billing")
        .annotate(
            domain_count=Count("domains", distinct=True),
            verified_count=Count("domains", filter=Q(domains__verified_at__isnull=False), distinct=True),
            member_count=Count("memberships", distinct=True),
            last_login=Max("memberships__user__last_login"),
        )
        .order_by("-created_at")
    )
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(owner__email__icontains=q) | Q(domains__name__icontains=q)).distinct()
    status = params.get("status")
    now = timezone.now()
    if status == "trialing":
        qs = qs.filter(billing__status=BillingAccount.Status.TRIALING, billing__trial_ends_at__gt=now)
    elif status in ("active", "past_due"):
        qs = qs.filter(billing__status=status).exclude(billing__stripe_subscription_id="")
    elif status == "manual":
        qs = qs.filter(billing__status__in=PAID, billing__stripe_subscription_id="")
    elif status == "canceled":
        qs = qs.filter(billing__status=status)
    elif status == "free":
        qs = qs.exclude(billing__status__in=PAID).exclude(
            billing__status=BillingAccount.Status.TRIALING, billing__trial_ends_at__gt=now
        )
    return qs


def _workspace_row(o: Organization) -> dict:
    return {
        "id": str(o.pk),
        "name": o.name,
        "owner": {"email": o.owner.email, "full_name": o.owner.full_name, "email_verified": o.owner.email_verified},
        "created_at": o.created_at,
        "status": o.status,
        "domains": o.domain_count,
        "verified_domains": o.verified_count,
        "members": o.member_count,
        "last_login": o.last_login,
        "billing": _billing(getattr(o, "billing", None)),
    }


def _csv(filename: str, header: list[str], rows) -> HttpResponse:
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    w = csv.writer(resp)
    w.writerow(header)
    for r in rows:
        # Neutralise spreadsheet formulas in user-supplied text.
        w.writerow(["'" + c if isinstance(c, str) and c[:1] in "=+-@\t\r" else c for c in r])
    return resp


class OverviewView(APIView):
    permission_classes = PERMS

    def get(self, request):
        now = timezone.now()
        users = User.objects.filter(is_active=True)
        orgs = Organization.objects.filter(is_demo=False)
        accounts = list(BillingAccount.objects.filter(organization__is_demo=False))
        by_plan: dict[str, int] = {}
        for b in accounts:
            if b.status in PAID and not _manual(b):
                by_plan[b.plan] = by_plan.get(b.plan, 0) + 1
        return Response(
            {
                "users": users.count(),
                "users_unverified": users.filter(email_verified=False).count(),
                "signups_7d": users.filter(created_at__gte=now - timedelta(days=7)).count(),
                "signups_30d": users.filter(created_at__gte=now - timedelta(days=30)).count(),
                "workspaces": orgs.count(),
                "trialing": sum(1 for b in accounts if b.trial_active),
                "paying": sum(1 for b in accounts if b.status == BillingAccount.Status.ACTIVE and not _manual(b)),
                "past_due": sum(1 for b in accounts if b.status == BillingAccount.Status.PAST_DUE and not _manual(b)),
                "manual": sum(1 for b in accounts if _manual(b)),
                "paying_by_plan": by_plan,
                "mrr": round(sum(_monthly_value(b) for b in accounts), 2),
                "domains": Domain.objects.filter(organization__is_demo=False).count(),
                "verified_domains": Domain.objects.filter(
                    organization__is_demo=False, verified_at__isnull=False
                ).count(),
                "trials_ending_7d": [
                    {"id": str(b.organization_id), "name": b.organization.name, "trial_ends_at": b.trial_ends_at}
                    for b in BillingAccount.objects.filter(
                        organization__is_demo=False,
                        status=BillingAccount.Status.TRIALING,
                        trial_ends_at__gt=now,
                        trial_ends_at__lte=now + timedelta(days=7),
                    )
                    .select_related("organization")
                    .order_by("trial_ends_at")[:20]
                ],
            }
        )


class WorkspaceListView(APIView):
    permission_classes = PERMS

    def get(self, request):
        qs = _workspaces(request.query_params)
        if request.query_params.get("export") == "csv":
            rows = [_workspace_row(o) for o in qs[:10000]]
            return _csv(
                "domainvitals-workspaces.csv",
                [
                    "Workspace",
                    "Owner",
                    "Owner name",
                    "Created",
                    "Plan",
                    "Status",
                    "Interval",
                    "Trial ends",
                    "Renews",
                    "Cancels",
                    "MRR (USD)",
                    "Domains",
                    "Verified",
                    "Members",
                    "Last sign-in",
                    "Stripe customer",
                ],
                [
                    [
                        r["name"],
                        r["owner"]["email"],
                        r["owner"]["full_name"],
                        r["created_at"].date().isoformat(),
                        r["billing"]["plan"],
                        r["billing"]["status"],
                        r["billing"]["interval"],
                        r["billing"]["trial_ends_at"] and r["billing"]["trial_ends_at"].date().isoformat(),
                        r["billing"]["current_period_end"] and r["billing"]["current_period_end"].date().isoformat(),
                        "yes" if r["billing"]["cancel_at_period_end"] else "",
                        r["billing"]["mrr"],
                        r["domains"],
                        r["verified_domains"],
                        r["members"],
                        r["last_login"] and r["last_login"].isoformat(timespec="minutes"),
                        r["billing"]["stripe_customer_id"],
                    ]
                    for r in rows
                ],
            )
        from common.pagination import StandardPagination

        pager = StandardPagination()
        page = pager.paginate_queryset(qs, request, view=self)
        return pager.get_paginated_response([_workspace_row(o) for o in page])


class WorkspaceDetailView(APIView):
    permission_classes = PERMS

    def get(self, request, org_id):
        o = get_object_or_404(_workspaces({}), pk=org_id)
        members = Membership.objects.filter(organization=o).select_related("user").order_by("created_at")
        domains = o.domains.select_related("latest_scan").order_by("name")
        return Response(
            {
                **_workspace_row(o),
                "timezone": o.timezone,
                "members": [
                    {
                        "email": m.user.email,
                        "full_name": m.user.full_name,
                        "role": m.role,
                        "joined_at": m.created_at,
                        "last_login": m.user.last_login,
                    }
                    for m in members
                ],
                "domain_list": [
                    {
                        "name": d.name,
                        "verified_at": d.verified_at,
                        "created_at": d.created_at,
                        "monitoring_enabled": d.monitoring_enabled,
                        "score": d.latest_scan.health_score if d.latest_scan else None,
                        "overall": d.latest_scan.overall_status if d.latest_scan else "",
                        "checked_at": d.latest_scan.completed_at if d.latest_scan else None,
                    }
                    for d in domains
                ],
            }
        )


class UserListView(APIView):
    permission_classes = PERMS

    def get(self, request):
        qs = User.objects.order_by("-created_at").prefetch_related(
            Prefetch(
                "memberships",
                queryset=Membership.objects.select_related("organization").filter(organization__is_demo=False),
            )
        )
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(full_name__icontains=q))
        if request.query_params.get("verified") in ("yes", "no"):
            qs = qs.filter(email_verified=request.query_params["verified"] == "yes")

        def row(u):
            return {
                "id": str(u.pk),
                "email": u.email,
                "full_name": u.full_name,
                "email_verified": u.email_verified,
                "is_staff": u.is_staff,
                "is_active": u.is_active,
                "created_at": u.created_at,
                "last_login": u.last_login,
                "terms_version": u.terms_version,
                "workspaces": [
                    {"id": str(m.organization_id), "name": m.organization.name, "role": m.role}
                    for m in u.memberships.all()
                ],
            }

        if request.query_params.get("export") == "csv":
            return _csv(
                "domainvitals-users.csv",
                ["Email", "Name", "Confirmed", "Signed up", "Last sign-in", "Terms version", "Workspaces"],
                [
                    [
                        u.email,
                        u.full_name,
                        "yes" if u.email_verified else "no",
                        u.created_at.date().isoformat(),
                        u.last_login and u.last_login.isoformat(timespec="minutes"),
                        u.terms_version,
                        "; ".join(f"{m.organization.name} ({m.role})" for m in u.memberships.all()),
                    ]
                    for u in qs[:10000]
                ],
            )
        from common.pagination import StandardPagination

        pager = StandardPagination()
        page = pager.paginate_queryset(qs, request, view=self)
        return pager.get_paginated_response([row(u) for u in page])
