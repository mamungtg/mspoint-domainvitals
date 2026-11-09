from django.db import models

from common.models import UUIDModel


class MonitoredHost(UUIDModel):
    """A hostname:port whose certificate is checked. Always the verified domain
    itself or one of its subdomains."""

    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="tls_hosts")
    hostname = models.CharField(max_length=253)
    port = models.PositiveIntegerField(default=443)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    latest_scan = models.ForeignKey(
        "ssl_monitor.SslScan", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["hostname", "port"]
        constraints = [models.UniqueConstraint(fields=["domain", "hostname", "port"], name="uniq_tls_host")]

    @property
    def label(self) -> str:
        return self.hostname if self.port == 443 else f"{self.hostname}:{self.port}"


class SslScan(UUIDModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"  # could not connect / blocked

    host = models.ForeignKey(MonitoredHost, on_delete=models.CASCADE, related_name="scans")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    trigger = models.CharField(max_length=12, default="manual")
    created_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result_status = models.CharField(max_length=8, blank=True)  # pass | warn | fail | error
    not_after = models.DateTimeField(null=True, blank=True, db_index=True)
    certificate = models.JSONField(default=dict, blank=True)  # CertInfo
    findings = models.JSONField(default=list, blank=True)
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["host", "-created_at"])]
