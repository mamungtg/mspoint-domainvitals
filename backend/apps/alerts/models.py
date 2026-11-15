import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models import TimestampedModel, UUIDModel


class Severity(models.TextChoices):
    CRITICAL = "critical", "Critical"
    WARNING = "warning", "Warning"
    INFO = "info", "Info"


SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


class Kind(models.TextChoices):
    CHECK = "check", "Failing checks"
    CERTIFICATE = "certificate", "Certificates"
    DNS_CHANGE = "dns_change", "DNS changes"
    DMARC_SENDER = "dmarc_sender", "New DMARC senders"


# Kinds that open and resolve. The others are one-off notices.
STATEFUL_KINDS = {Kind.CHECK, Kind.CERTIFICATE}


class Alert(UUIDModel):
    """A problem (open until it is fixed) or a notice (a one-off event)."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        NOTICE = "notice", "Notice"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="alerts")
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    key = models.CharField(max_length=200)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    title = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "key"], condition=Q(status="open"), name="uniq_open_alert_per_key"
            ),
        ]
        indexes = [models.Index(fields=["organization", "status", "opened_at"])]

    def __str__(self):
        return f"[{self.severity}] {self.title}"


class Channel(TimestampedModel):
    class Type(models.TextChoices):
        EMAIL = "email", "Email"
        SLACK = "slack", "Slack"
        TEAMS = "teams", "Microsoft Teams"
        WEBHOOK = "webhook", "Webhook"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="alert_channels"
    )
    type = models.CharField(max_length=10, choices=Type.choices)
    name = models.CharField(max_length=80)
    enabled = models.BooleanField(default=True)
    url = models.URLField(max_length=500, blank=True)
    notify_managers = models.BooleanField(default=False)  # email: all owners and admins
    recipients = models.JSONField(default=list, blank=True)  # email: extra addresses
    events = models.JSONField(default=list, blank=True)
    min_severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    secret = models.CharField(max_length=64, default=secrets.token_hex, editable=False)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_type_display()}: {self.name}"


class Delivery(UUIDModel):
    class Event(models.TextChoices):
        OPENED = "opened", "Opened"
        ESCALATED = "escalated", "Escalated"
        RESOLVED = "resolved", "Resolved"
        NOTICE = "notice", "Notice"
        TEST = "test", "Test"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    alert = models.ForeignKey(Alert, null=True, blank=True, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=10, choices=Event.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event} via {self.channel_id}: {self.status}"
