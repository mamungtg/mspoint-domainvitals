from urllib.parse import urlsplit

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers

from .models import Alert, Channel, Kind

TEAMS_HOSTS = (".webhook.office.com", ".logic.azure.com", ".powerplatform.com", ".powerautomate.com")
MAX_RECIPIENTS = 10


class AlertSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source="domain.name", default=None, read_only=True)
    acknowledged_by = serializers.CharField(source="acknowledged_by.email", default=None, read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id",
            "kind",
            "severity",
            "status",
            "title",
            "detail",
            "domain",
            "domain_name",
            "opened_at",
            "updated_at",
            "resolved_at",
            "acknowledged_by",
            "acknowledged_at",
        ]
        read_only_fields = fields


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = [
            "id",
            "type",
            "name",
            "enabled",
            "url",
            "notify_managers",
            "recipients",
            "events",
            "min_severity",
            "secret",
            "last_sent_at",
            "last_error",
            "created_at",
        ]
        read_only_fields = ["id", "secret", "last_sent_at", "last_error", "created_at"]

    def validate_events(self, value):
        valid = {k.value for k in Kind}
        bad = [v for v in value if v not in valid]
        if bad or not value:
            raise serializers.ValidationError("Choose at least one event type.")
        return sorted(set(value))

    def validate_recipients(self, value):
        out = []
        for v in value:
            v = str(v).strip().lower()
            try:
                validate_email(v)
            except DjangoValidationError:
                raise serializers.ValidationError(f"{v} is not a valid email address.") from None
            out.append(v)
        if len(set(out)) > MAX_RECIPIENTS:
            raise serializers.ValidationError(f"Use up to {MAX_RECIPIENTS} addresses.")
        return sorted(set(out))

    def validate(self, attrs):
        t = attrs.get("type", getattr(self.instance, "type", None))
        if self.instance and "type" in attrs and attrs["type"] != self.instance.type:
            raise serializers.ValidationError({"type": ["The channel type cannot be changed."]})
        url = attrs.get("url", getattr(self.instance, "url", ""))
        if t == Channel.Type.EMAIL:
            attrs["url"] = ""
            managers = attrs.get("notify_managers", getattr(self.instance, "notify_managers", False))
            recipients = attrs.get("recipients", getattr(self.instance, "recipients", []))
            if not managers and not recipients:
                raise serializers.ValidationError(
                    {"recipients": ["Add at least one address or include owners and admins."]}
                )
            return attrs
        parts = urlsplit(url or "")
        if parts.scheme != "https" or not parts.hostname:
            raise serializers.ValidationError({"url": ["Enter the https:// URL from the app."]})
        host = parts.hostname.lower()
        if t == Channel.Type.SLACK and host != "hooks.slack.com":
            raise serializers.ValidationError(
                {"url": ["Use a Slack incoming webhook URL (https://hooks.slack.com/...)."]}
            )
        if t == Channel.Type.TEAMS and not host.endswith(TEAMS_HOSTS):
            raise serializers.ValidationError(
                {
                    "url": [
                        "Use the webhook URL from a Teams Workflow (Post to a channel when a webhook request is received)."
                    ]
                }
            )
        attrs["notify_managers"], attrs["recipients"] = False, []
        return attrs
