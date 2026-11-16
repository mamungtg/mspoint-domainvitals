from django.core.validators import RegexValidator
from django.db import models

HEX = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use a colour like #14508F.")


class ReportBranding(models.Model):
    """White-label settings for a workspace's PDF reports."""

    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="report_branding"
    )
    company_name = models.CharField(max_length=80, blank=True)
    accent_color = models.CharField(max_length=7, default="#14508F", validators=[HEX])
    footer_text = models.CharField(max_length=200, blank=True)
    # Re-encoded PNG, at most 600x200 px; kept in the database (small, no media volume needed).
    logo = models.BinaryField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Branding for {self.organization_id}"


class ReportSchedule(models.Model):
    """A monthly PDF report emailed on the 1st."""

    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="report_schedule"
    )
    enabled = models.BooleanField(default=False)
    recipients = models.JSONField(default=list, blank=True)
    last_sent_on = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Monthly report for {self.organization_id}"
