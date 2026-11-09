from django.db import models

from common.models import UUIDModel


class DnsScan(UUIDModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        SCHEDULE = "schedule", "Scheduled"
        VERIFICATION = "verification", "After verification"
        DEMO = "demo", "Sample data"

    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="scans")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    trigger = models.CharField(max_length=16, choices=Trigger.choices, default=Trigger.MANUAL)
    health_score = models.PositiveSmallIntegerField(null=True, blank=True)
    overall_status = models.CharField(max_length=8, blank=True)  # pass | warn | fail | error
    critical_count = models.PositiveSmallIntegerField(default=0)
    warning_count = models.PositiveSmallIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)  # {"spf": "pass", ...}
    results = models.JSONField(default=dict, blank=True)  # full check results with findings
    # Record inventory at scan time: {"<name> <TYPE>": {"ttl": int, "values": [...]}}
    records = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["domain", "-created_at"])]

    def __str__(self):
        return f"{self.domain} {self.created_at:%Y-%m-%d %H:%M} {self.status}"


class DnsChange(UUIDModel):
    """One record set that differs from the previous completed scan."""

    class Kind(models.TextChoices):
        ADDED = "added", "Added"
        REMOVED = "removed", "Removed"
        CHANGED = "changed", "Changed"
        TTL = "ttl", "TTL changed"

    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="dns_changes")
    scan = models.ForeignKey(DnsScan, on_delete=models.CASCADE, related_name="changes")
    name = models.CharField(max_length=253)
    rtype = models.CharField(max_length=10)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    old_values = models.JSONField(default=list, blank=True)
    new_values = models.JSONField(default=list, blank=True)
    old_ttl = models.PositiveIntegerField(null=True, blank=True)
    new_ttl = models.PositiveIntegerField(null=True, blank=True)
    detected_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-detected_at", "name", "rtype"]
        indexes = [models.Index(fields=["domain", "-detected_at"]), models.Index(fields=["domain", "name", "rtype"])]
