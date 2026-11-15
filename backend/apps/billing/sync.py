"""Apply Stripe webhook events to BillingAccount. Stripe is the source of truth:
every subscription event re-reads the subscription and overwrites our copy."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.db import IntegrityError, transaction

from common.mail import send_branded

from . import stripe_api
from .models import BillingAccount, StripeEvent
from .plans import PLANS, parse_lookup_key

log = logging.getLogger(__name__)

STATUS = {
    "active": BillingAccount.Status.ACTIVE,
    "trialing": BillingAccount.Status.ACTIVE,
    "past_due": BillingAccount.Status.PAST_DUE,
    "unpaid": BillingAccount.Status.PAST_DUE,
    "canceled": BillingAccount.Status.CANCELED,
    "incomplete_expired": BillingAccount.Status.CANCELED,
}


def _get(obj, key, default=None):
    try:
        return obj[key]
    except (KeyError, TypeError):
        return getattr(obj, key, default)


def _ts(v):
    return datetime.fromtimestamp(v, UTC) if v else None


def account_for_subscription(sub) -> BillingAccount | None:
    org_id = (_get(sub, "metadata") or {}).get("org_id")
    if org_id:
        acc = BillingAccount.objects.filter(organization_id=org_id).first()
        if acc:
            return acc
    return BillingAccount.objects.filter(stripe_customer_id=_get(sub, "customer")).first()


def apply_subscription(sub) -> BillingAccount | None:
    acc = account_for_subscription(sub)
    if acc is None:
        log.warning("stripe: subscription %s matches no workspace", _get(sub, "id"))
        return None
    status = STATUS.get(_get(sub, "status"))
    if status is None:  # incomplete: checkout not finished yet
        return acc
    items = (_get(sub, "items") or {}).get("data") or []
    item = items[0] if items else {}
    parsed = parse_lookup_key(_get(_get(item, "price") or {}, "lookup_key"))
    # A newer subscription for the same workspace wins; ignore late events for an old one.
    if (
        acc.stripe_subscription_id
        and acc.stripe_subscription_id != _get(sub, "id")
        and status == BillingAccount.Status.CANCELED
    ):
        return acc
    acc.stripe_customer_id = _get(sub, "customer") or acc.stripe_customer_id
    acc.stripe_subscription_id = _get(sub, "id")
    acc.status = status
    if status == BillingAccount.Status.CANCELED:
        acc.plan, acc.interval = "free", ""
    elif parsed:
        acc.plan, acc.interval = parsed
    acc.current_period_end = _ts(_get(sub, "current_period_end") or _get(item, "current_period_end"))
    acc.cancel_at_period_end = bool(_get(sub, "cancel_at_period_end"))
    acc.trial_ends_at = None
    acc.save()
    return acc


def _notify_payment_failed(acc: BillingAccount) -> None:
    from django.conf import settings

    from apps.organizations.models import Role

    org = acc.organization
    for email in org.memberships.filter(role=Role.OWNER, user__email_verified=True).values_list(
        "user__email", flat=True
    ):
        send_branded(
            to=email,
            subject="Payment failed for your DomainVitals subscription",
            heading="We couldn't take your payment",
            paragraphs=[
                f"The latest payment for the {PLANS[acc.plan]['name']} plan of {org.name} did not go through. "
                "Stripe will retry over the next days. Update the card to keep monitoring without interruption."
            ],
            button=("Update payment method", f"{settings.FRONTEND_URL}/settings/billing"),
            note="If the payment keeps failing, the workspace moves to the Free plan. Nothing is deleted.",
            fail_silently=True,
        )


def handle_event(event) -> str:
    """Process one verified event. Returns a short outcome for logging."""
    try:
        with transaction.atomic():
            StripeEvent.objects.create(id=event["id"], type=event["type"])
    except IntegrityError:
        return "duplicate"
    obj = event["data"]["object"]
    etype = event["type"]
    if etype == "checkout.session.completed" and _get(obj, "mode") == "subscription":
        sub = stripe_api.retrieve_subscription(_get(obj, "subscription"))
        apply_subscription(sub)
        return "subscription synced"
    if etype.startswith("customer.subscription."):
        apply_subscription(obj)
        return "subscription synced"
    if etype == "invoice.payment_failed":
        sub_id = _get(obj, "subscription")
        if sub_id:
            acc = apply_subscription(stripe_api.retrieve_subscription(sub_id))
            if acc:
                _notify_payment_failed(acc)
        return "payment failed"
    return "ignored"
