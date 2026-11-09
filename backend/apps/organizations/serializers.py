from rest_framework import serializers

from apps.accounts.models import normalize_email_address

from .models import Invitation, Membership, Organization, Role


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "timezone", "status", "is_demo", "role", "created_at"]
        read_only_fields = ["id", "slug", "status", "is_demo", "role", "created_at"]

    def get_role(self, obj):
        roles = self.context.get("roles") or {}
        return roles.get(obj.pk)


class MemberUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()


class MembershipSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class RoleChangeSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices, default=Role.MEMBER)

    def validate_email(self, value):
        return normalize_email_address(value)


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = serializers.EmailField(source="invited_by.email", read_only=True, default=None)

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "invited_by", "created_at", "expires_at"]


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
