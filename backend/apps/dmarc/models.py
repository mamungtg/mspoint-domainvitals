from django.db import models

from common.models import UUIDModel


class DmarcReport(UUIDModel):
    """One aggregate (RUA) report from one receiver for one domain and period.

    Reports are keyed by domain name rather than a Domain row: the same domain
    can be verified in more than one workspace (an agency and its client), and
    each of them sees the same reports.
    """

    class Source(models.TextChoices):
        MAIL = "mail", "Mailbox"
        UPLOAD = "upload", "Upload"
        DEMO = "demo", "Sample data"

    domain_name = models.CharField(max_length=253, db_index=True)
    reporter = models.CharField(max_length=255)
    reporter_email = models.CharField(max_length=255, blank=True)
    report_id = models.CharField(max_length=255)
    date_begin = models.DateTimeField()
    date_end = models.DateTimeField()
    policy = models.JSONField(default=dict, blank=True)
    message_count = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MAIL)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_begin"]
        constraints = [
            models.UniqueConstraint(fields=["domain_name", "reporter", "report_id"], name="uniq_dmarc_report"),
        ]
        indexes = [models.Index(fields=["domain_name", "date_begin"])]

    def __str__(self):
        return f"{self.domain_name} from {self.reporter} ({self.report_id})"


class DmarcRecord(models.Model):
    """One <record> row: a sending IP and how its messages were evaluated."""

    report = models.ForeignKey(DmarcReport, on_delete=models.CASCADE, related_name="records")
    domain_name = models.CharField(max_length=253)
    day = models.DateField()
    source_ip = models.GenericIPAddressField()
    count = models.PositiveIntegerField()
    disposition = models.CharField(max_length=20, blank=True)
    dkim_aligned = models.BooleanField(default=False)
    spf_aligned = models.BooleanField(default=False)
    header_from = models.CharField(max_length=253, blank=True)
    envelope_from = models.CharField(max_length=253, blank=True)
    dkim = models.JSONField(default=list, blank=True)
    spf = models.JSONField(default=list, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain_name", "day"]),
            models.Index(fields=["source_ip"]),
        ]

    def __str__(self):
        return f"{self.source_ip} x{self.count} for {self.domain_name}"

    @property
    def passed(self) -> bool:
        return self.dkim_aligned or self.spf_aligned


class SourceIp(models.Model):
    """Reverse DNS and the sending service behind an IP, cached for 30 days."""

    ip = models.GenericIPAddressField(primary_key=True)
    ptr = models.CharField(max_length=253, blank=True)
    provider = models.CharField(max_length=80, blank=True)
    looked_up_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.ip} {self.provider or self.ptr}"
