from rest_framework import serializers

from apps.domains.validation import InvalidDomain, normalize_domain


class AddHostSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=253)
    port = serializers.IntegerField(min_value=1, max_value=65535, default=443)

    def validate_hostname(self, value):
        try:
            return normalize_domain(value)
        except InvalidDomain as exc:
            raise serializers.ValidationError(str(exc)) from exc


class HostScanSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    result_status = serializers.CharField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
    not_after = serializers.DateTimeField(allow_null=True)
    certificate = serializers.JSONField()
    findings = serializers.JSONField()
    error = serializers.CharField()
