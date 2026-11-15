"""Thin wrapper around the Stripe SDK so the rest of the app (and the tests)
never import stripe directly."""

from __future__ import annotations

import stripe
from django.conf import settings
from django.core.cache import cache

from .plans import lookup_key


class BillingNotConfigured(Exception):
    pass


def client():
    if not settings.STRIPE_SECRET_KEY:
        raise BillingNotConfigured("Online payments are not set up yet.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.max_network_retries = 2
    return stripe


def configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET)


def price_id(plan: str, interval: str) -> str:
    key = lookup_key(plan, interval)
    cached = cache.get(f"stripe:price:{key}")
    if cached:
        return cached
    prices = client().Price.list(lookup_keys=[key], active=True, limit=1).data
    if not prices:
        raise BillingNotConfigured(f"No Stripe price with lookup key {key}. Run manage.py stripe_setup.")
    cache.set(f"stripe:price:{key}", prices[0].id, 3600)
    return prices[0].id


def ensure_customer(account, email: str) -> str:
    if account.stripe_customer_id:
        return account.stripe_customer_id
    org = account.organization
    cust = client().Customer.create(
        email=email, name=org.name, metadata={"org_id": str(org.pk)}, idempotency_key=f"dv-customer-{org.pk}"
    )
    account.stripe_customer_id = cust.id
    account.save(update_fields=["stripe_customer_id", "updated_at"])
    return cust.id


def checkout_url(account, plan: str, interval: str, email: str) -> str:
    org = account.organization
    base = f"{settings.FRONTEND_URL}/settings/billing"
    params = {
        "mode": "subscription",
        "customer": ensure_customer(account, email),
        "client_reference_id": str(org.pk),
        "line_items": [{"price": price_id(plan, interval), "quantity": 1}],
        "subscription_data": {"metadata": {"org_id": str(org.pk)}},
        "success_url": f"{base}?checkout=success",
        "cancel_url": f"{base}?checkout=cancel",
        "allow_promotion_codes": True,
        "billing_address_collection": "required",
        "tax_id_collection": {"enabled": True},
        "customer_update": {"address": "auto", "name": "auto"},
    }
    if settings.STRIPE_AUTOMATIC_TAX:
        params["automatic_tax"] = {"enabled": True}
    return client().checkout.Session.create(**params).url


def portal_url(account) -> str:
    params = {"customer": account.stripe_customer_id, "return_url": f"{settings.FRONTEND_URL}/settings/billing"}
    conf = cache.get("stripe:portal-config")
    if conf is None:
        confs = [
            c
            for c in client().billing_portal.Configuration.list(active=True, limit=20).data
            if (c.metadata or {}).get("dv") == "1"
        ]
        conf = confs[0].id if confs else ""
        cache.set("stripe:portal-config", conf, 3600)
    if conf:
        params["configuration"] = conf
    return client().billing_portal.Session.create(**params).url


def construct_event(payload: bytes, signature: str):
    return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)


def retrieve_subscription(sub_id: str):
    return client().Subscription.retrieve(sub_id)
