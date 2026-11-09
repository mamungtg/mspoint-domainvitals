import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import TimestampedModel


def new_verification_token() -> str:
    return secrets.token_hex(16)


class Domain(TimestampedModel):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="domains")
    name = models.CharField(max_length=253)
    verification_token = models.CharField(max_length=64, default=new_verification_token)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_checked_at = models.DateTimeField(null=True, blank=True)
    verification_failing_since = models.DateTimeField(null=True, blank=True)
    monitoring_enabled = models.BooleanField(default=True)
    dkim_selectors = models.JSONField(default=list, blank=True)
    # Extra host names whose A/AAAA/CNAME records are tracked (www.<domain> is always included).
    dns_watch_names = models.JSONField(default=list, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    latest_scan = models.ForeignKey(
        "dns_monitor.DnsScan", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="uniq_domain_per_org")]
        indexes = [models.Index(fields=["verified_at", "monitoring_enabled"])]

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    @property
    def verification_host(self) -> str:
        return f"_domainvitals.{self.name}"

    @property
    def verification_value(self) -> str:
        return f"domainvitals-verify={self.verification_token}"

    def mark_verified(self):
        now = timezone.now()
        self.verified_at = self.verified_at or now
        self.verification_checked_at = now
        self.verification_failing_since = None

    def __str__(self):
        return self.name
