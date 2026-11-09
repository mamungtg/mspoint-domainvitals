from rest_framework import serializers

from apps.dns_monitor.checks.dkim import SELECTOR_RE
from apps.dns_monitor.models import DnsScan

from .models import Domain
from .validation import InvalidDomain, normalize_domain


class ScanSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DnsScan
        fields = [
            "id",
            "status",
            "trigger",
            "health_score",
            "overall_status",
            "critical_count",
            "warning_count",
            "summary",
            "created_at",
            "completed_at",
        ]


class ScanDetailSerializer(ScanSummarySerializer):
    class Meta(ScanSummarySerializer.Meta):
        fields = ScanSummarySerializer.Meta.fields + ["results", "error", "started_at"]


class DomainSerializer(serializers.ModelSerializer):
    latest_scan = ScanSummarySerializer(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    verification = serializers.SerializerMethodField()

    class Meta:
        model = Domain
        fields = [
            "id",
            "name",
            "is_verified",
            "verified_at",
            "monitoring_enabled",
            "dkim_selectors",
            "verification",
            "latest_scan",
            "created_at",
        ]
        read_only_fields = ["id", "name", "is_verified", "verified_at", "latest_scan", "created_at"]

    def get_verification(self, obj):
        return {
            "type": "TXT",
            "host": obj.verification_host,
            "value": obj.verification_value,
            "failing_since": obj.verification_failing_since,
        }

    def validate_dkim_selectors(self, value):
        if not isinstance(value, list) or len(value) > 10:
            raise serializers.ValidationError("Provide up to 10 selectors.")
        cleaned = []
        for s in value:
            s = str(s).strip().lower()
            if not SELECTOR_RE.match(s):
                raise serializers.ValidationError(f"'{s}' is not a valid DKIM selector.")
            if s not in cleaned:
                cleaned.append(s)
        return cleaned


class AddDomainSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=300)

    def validate_name(self, value):
        try:
            return normalize_domain(value)
        except InvalidDomain as exc:
            raise serializers.ValidationError(str(exc)) from exc


class ToolCheckSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=300)
    check = serializers.ChoiceField(choices=["all", "spf", "dmarc", "dkim", "mx"], default="all")
    selector = serializers.CharField(max_length=63, required=False, allow_blank=True)

    def validate_domain(self, value):
        try:
            return normalize_domain(value)
        except InvalidDomain as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_selector(self, value):
        value = value.strip().lower()
        if value and not SELECTOR_RE.match(value):
            raise serializers.ValidationError("Not a valid DKIM selector.")
        return value
