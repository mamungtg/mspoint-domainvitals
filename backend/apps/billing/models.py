from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from .plans import PLANS, TRIAL_PLAN


class BillingAccount(models.Model):
    class Status(models.TextChoices):
        FREE = "free", "Free"
        TRIALING = "trialing", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Payment overdue"
        CANCELED = "canceled", "Canceled"

    organization = models.OneToOneField("organizations.Organization", on_delete=models.CASCADE, related_name="billing")
    plan = models.CharField(max_length=20, default="free")
    interval = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.FREE)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=64, blank=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=64, blank=True, db_index=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    # Manual overrides (Enterprise contracts, support): {"domains": 500, "members": null}
    custom_limits = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization_id}: {self.plan} ({self.status})"

    @classmethod
    def start_trial(cls, org):
        days = getattr(settings, "BILLING_TRIAL_DAYS", 14)
        if days <= 0:
            return cls.objects.create(organization=org)
        return cls.objects.create(
            organization=org,
            plan=TRIAL_PLAN,
            status=cls.Status.TRIALING,
            trial_ends_at=timezone.now() + timedelta(days=days),
        )

    @property
    def trial_active(self) -> bool:
        return (
            self.status == self.Status.TRIALING
            and self.trial_ends_at is not None
            and self.trial_ends_at > timezone.now()
        )

    @property
    def effective_plan(self) -> str:
        """The plan whose limits apply right now."""
        if self.status == self.Status.TRIALING:
            return self.plan if self.trial_active else "free"
        if self.status in (self.Status.ACTIVE, self.Status.PAST_DUE):
            return self.plan
        return "free"

    def limits(self) -> dict:
        p = PLANS.get(self.effective_plan, PLANS["free"])
        out = {k: p[k] for k in ("domains", "members", "channels", "dmarc_days")}
        out.update({k: v for k, v in (self.custom_limits or {}).items() if k in out})
        return out


class StripeEvent(models.Model):
    """Processed webhook events, so a redelivered event is applied once."""

    id = models.CharField(max_length=80, primary_key=True)
    type = models.CharField(max_length=80)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id} {self.type}"
