"""Plan limits, checked where things are added. Nothing is ever deleted when a
workspace is over its limit: adding is blocked and scheduled scans cover the
first N domains."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from .models import BillingAccount
from .plans import PLANS


class PlanLimit(PermissionDenied):
    default_code = "plan_limit"


def account_for(org) -> BillingAccount | None:
    if org.is_demo:
        return None
    acc = getattr(org, "_billing_cache", None)
    if acc is None:
        acc = BillingAccount.objects.filter(organization=org).first() or BillingAccount.objects.create(organization=org)
        org._billing_cache = acc
    return acc


def limits_for(org) -> dict:
    acc = account_for(org)
    return (
        acc.limits() if acc else {k: PLANS["enterprise"][k] for k in ("domains", "members", "channels", "dmarc_days")}
    )


def plan_name(org) -> str:
    acc = account_for(org)
    return PLANS[acc.effective_plan]["name"] if acc else "Demo"


def check_domains(org) -> None:
    limit = limits_for(org)["domains"]
    if limit is not None and org.domains.count() >= limit:
        raise PlanLimit(
            f"The {plan_name(org)} plan includes {limit} domain{'s' if limit != 1 else ''}. Upgrade the plan to add more."
        )


def check_members(org) -> None:
    from apps.organizations.models import Invitation

    limit = limits_for(org)["members"]
    if limit is None:
        return
    used = org.memberships.count() + Invitation.objects.pending().filter(organization=org).count()
    if used >= limit:
        raise PlanLimit(
            f"The {plan_name(org)} plan includes {limit} team member{'s' if limit != 1 else ''}. Upgrade the plan to invite more."
        )


def check_channel(org, channel_type: str) -> None:
    if channel_type not in limits_for(org)["channels"]:
        raise PlanLimit(f"{channel_type.capitalize()} notifications are not included in the {plan_name(org)} plan.")


def check_dmarc_days(org, days: int) -> None:
    if days > limits_for(org)["dmarc_days"]:
        raise PlanLimit(f"The {plan_name(org)} plan keeps {limits_for(org)['dmarc_days']} days of DMARC history.")


def monitored_domain_ids(org) -> set:
    """Verified domains covered by scheduled monitoring (oldest first, up to the limit)."""
    limit = limits_for(org)["domains"]
    qs = org.domains.filter(verified_at__isnull=False).order_by("created_at").values_list("id", flat=True)
    return set(qs if limit is None else qs[:limit])


def usage(org) -> dict:
    from apps.organizations.models import Invitation

    return {
        "domains": org.domains.count(),
        "members": org.memberships.count(),
        "pending_invitations": Invitation.objects.pending().filter(organization=org).count(),
    }
