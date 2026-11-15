"""The plan catalogue. Prices here are for display; Stripe holds the real ones
(created by `manage.py stripe_setup` with lookup keys dv_<plan>_<interval>ly)."""

from __future__ import annotations

ALL_CHANNELS = ["email", "slack", "teams", "webhook"]

PLANS: dict[str, dict] = {
    "free": {
        "name": "Free",
        "price": {"month": 0, "year": 0},
        "domains": 1,
        "members": 1,
        "channels": ["email"],
        "dmarc_days": 30,
        "summary": "One domain, for trying DomainVitals.",
    },
    "starter": {
        "name": "Starter",
        "price": {"month": 19, "year": 190},
        "domains": 5,
        "members": 3,
        "channels": ["email", "slack", "teams"],
        "dmarc_days": 90,
        "summary": "For small businesses and consultants.",
    },
    "agency": {
        "name": "Agency",
        "price": {"month": 79, "year": 790},
        "domains": 25,
        "members": 10,
        "channels": ALL_CHANNELS,
        "dmarc_days": 90,
        "summary": "For agencies looking after client domains.",
    },
    "msp": {
        "name": "MSP",
        "price": {"month": 199, "year": 1990},
        "domains": 100,
        "members": None,  # unlimited
        "channels": ALL_CHANNELS,
        "dmarc_days": 90,
        "summary": "For MSPs and hosting companies.",
    },
    "enterprise": {
        "name": "Enterprise",
        "price": None,  # custom contract
        "domains": 1000,
        "members": None,
        "channels": ALL_CHANNELS,
        "dmarc_days": 90,
        "summary": "Custom volume, invoicing and support.",
    },
}

PAID = ("starter", "agency", "msp")
INTERVALS = ("month", "year")
TRIAL_PLAN = "agency"


def lookup_key(plan: str, interval: str) -> str:
    return f"dv_{plan}_{interval}ly"


def parse_lookup_key(key: str | None) -> tuple[str, str] | None:
    if not key or not key.startswith("dv_"):
        return None
    try:
        _, plan, interval = key.split("_")
    except ValueError:
        return None
    interval = interval.removesuffix("ly")
    if plan in PAID and interval in INTERVALS:
        return plan, interval
    return None
