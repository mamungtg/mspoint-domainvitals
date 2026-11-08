from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record

from . import serializers as s
from .models import MANAGER_ROLES, ROLE_RANK, Invitation, Membership, Role, hash_token
from .permissions import get_membership_or_404, organizations_for


def _roles_map(user):
    return dict(Membership.objects.filter(user=user).values_list("organization_id", "role"))


class OrganizationListCreateView(APIView):
    @extend_schema(responses={200: s.OrganizationSerializer(many=True)}, tags=["organizations"])
    def get(self, request):
        qs = organizations_for(request.user).order_by("name")
        ctx = {"roles": _roles_map(request.user)}
        return Response(s.OrganizationSerializer(qs, many=True, context=ctx).data)

    @extend_schema(request=s.OrganizationSerializer, responses={201: s.OrganizationSerializer}, tags=["organizations"])
    def post(self, request):
        ser = s.OrganizationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = ser.save(owner=request.user)
        Membership.objects.create(organization=org, user=request.user, role=Role.OWNER)
        record(request, "organization.created", obj=org, organization=org)
        return Response(
            s.OrganizationSerializer(org, context={"roles": {org.pk: Role.OWNER}}).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationDetailView(APIView):
    @extend_schema(responses={200: s.OrganizationSerializer}, tags=["organizations"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        return Response(s.OrganizationSerializer(m.organization, context={"roles": {org_id: m.role}}).data)

    @extend_schema(request=s.OrganizationSerializer, responses={200: s.OrganizationSerializer}, tags=["organizations"])
    def patch(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        if m.role not in MANAGER_ROLES:
            raise PermissionDenied("Only workspace owners and admins can change settings.")
        ser = s.OrganizationSerializer(m.organization, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        record(
            request,
            "organization.updated",
            obj=m.organization,
            organization=m.organization,
            metadata={"fields": sorted(request.data.keys())},
        )
        return Response(s.OrganizationSerializer(m.organization, context={"roles": {org_id: m.role}}).data)


class MemberListInviteView(APIView):
    """GET lists members; POST invites a new member by email."""

    throttle_scope = None

    def get_throttles(self):
        self.throttle_scope = "invite" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(responses={200: s.MembershipSerializer(many=True)}, tags=["organizations"])
    def get(self, request, org_id):
        get_membership_or_404(request.user, org_id)
        qs = Membership.objects.filter(organization_id=org_id).select_related("user").order_by("created_at")
        return Response(s.MembershipSerializer(qs, many=True).data)

    @extend_schema(request=s.InviteSerializer, responses={201: s.InvitationSerializer}, tags=["organizations"])
    def post(self, request, org_id):
        actor = get_membership_or_404(request.user, org_id)
        if actor.role not in MANAGER_ROLES:
            raise PermissionDenied("Only workspace owners and admins can invite members.")
        ser = s.InviteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email, role = ser.validated_data["email"], ser.validated_data["role"]
        if ROLE_RANK[role] > actor.rank:
            raise PermissionDenied("You cannot invite someone with a higher role than your own.")
        if Membership.objects.filter(organization_id=org_id, user__email=email).exists():
            raise ValidationError({"email": ["This person is already a member."]})
        try:
            with transaction.atomic():
                inv, raw = Invitation.issue(
                    organization=actor.organization, email=email, role=role, invited_by=request.user
                )
        except IntegrityError:
            raise ValidationError({"email": ["An invitation is already pending for this address."]}) from None
        record(
            request,
            "organization.member_invited",
            obj=inv,
            organization=actor.organization,
            metadata={"email": email, "role": role},
        )
        org_name, inviter = actor.organization.name, request.user.email
        transaction.on_commit(lambda: _send_invitation(email, raw, org_name, inviter))
        return Response(s.InvitationSerializer(inv).data, status=status.HTTP_201_CREATED)


def _send_invitation(email, raw_token, org_name, inviter):
    link = f"{settings.FRONTEND_URL}/invite/accept?token={raw_token}"
    send_mail(
        subject=f"You've been invited to {org_name} on DomainVitals",
        message=f"{inviter} invited you to join the {org_name} workspace on DomainVitals.\n\n"
        f"Accept the invitation:\n{link}\n\nThis link expires in {settings.INVITATION_MAX_AGE_DAYS} days.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )


class InvitationListView(APIView):
    @extend_schema(responses={200: s.InvitationSerializer(many=True)}, tags=["organizations"])
    def get(self, request, org_id):
        actor = get_membership_or_404(request.user, org_id)
        if actor.role not in MANAGER_ROLES:
            raise PermissionDenied()
        qs = Invitation.objects.pending().filter(organization_id=org_id).select_related("invited_by")
        return Response(s.InvitationSerializer(qs, many=True).data)


class InvitationRevokeView(APIView):
    @extend_schema(responses={204: None}, tags=["organizations"])
    def delete(self, request, invitation_id):
        inv = get_object_or_404(Invitation.objects.pending(), pk=invitation_id)
        actor = get_membership_or_404(request.user, inv.organization_id)  # 404 for outsiders
        if actor.role not in MANAGER_ROLES:
            raise PermissionDenied()
        inv.revoked_at = timezone.now()
        inv.save(update_fields=["revoked_at"])
        record(request, "organization.invitation_revoked", obj=inv, organization=inv.organization)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationAcceptView(APIView):
    @extend_schema(
        request=s.AcceptInvitationSerializer, responses={200: s.OrganizationSerializer}, tags=["organizations"]
    )
    def post(self, request):
        ser = s.AcceptInvitationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        inv = (
            Invitation.objects.pending()
            .select_for_update()
            .select_related("organization")
            .filter(token_hash=hash_token(ser.validated_data["token"]))
            .first()
        )
        # The invitation is bound to the address it was sent to.
        if inv is None or inv.email != request.user.email:
            raise ValidationError({"token": ["This invitation is invalid, expired or for a different account."]})
        if not request.user.email_verified:
            raise PermissionDenied("Verify your email address before joining a workspace.")
        membership, created = Membership.objects.get_or_create(
            organization=inv.organization, user=request.user, defaults={"role": inv.role}
        )
        inv.accepted_at = timezone.now()
        inv.save(update_fields=["accepted_at"])
        record(request, "organization.member_joined", obj=membership, organization=inv.organization)
        return Response(
            s.OrganizationSerializer(inv.organization, context={"roles": {inv.organization_id: membership.role}}).data
        )


class MembershipDetailView(APIView):
    def _load(self, request, membership_id):
        target = get_object_or_404(Membership.objects.select_related("organization", "user"), pk=membership_id)
        actor = get_membership_or_404(request.user, target.organization_id)  # outsiders get 404
        return actor, target

    @staticmethod
    def _owner_count(org_id):
        return Membership.objects.filter(organization_id=org_id, role=Role.OWNER).count()

    @extend_schema(request=s.RoleChangeSerializer, responses={200: s.MembershipSerializer}, tags=["organizations"])
    def patch(self, request, membership_id):
        actor, target = self._load(request, membership_id)
        ser = s.RoleChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_role = ser.validated_data["role"]
        if actor.role not in MANAGER_ROLES:
            raise PermissionDenied("Only workspace owners and admins can change roles.")
        if actor.role != Role.OWNER and (target.role == Role.OWNER or new_role == Role.OWNER):
            raise PermissionDenied("Only an owner can grant or change the owner role.")
        if target.role == Role.OWNER and new_role != Role.OWNER and self._owner_count(target.organization_id) <= 1:
            raise ValidationError({"role": ["A workspace must keep at least one owner."]})
        old = target.role
        target.role = new_role
        target.save(update_fields=["role"])
        record(
            request,
            "organization.role_changed",
            obj=target,
            organization=target.organization,
            metadata={"user": target.user.email, "from": old, "to": new_role},
        )
        return Response(s.MembershipSerializer(target).data)

    @extend_schema(responses={204: None}, tags=["organizations"])
    def delete(self, request, membership_id):
        actor, target = self._load(request, membership_id)
        leaving_self = target.user_id == request.user.pk
        if not leaving_self:
            if actor.role not in MANAGER_ROLES:
                raise PermissionDenied("Only workspace owners and admins can remove members.")
            if actor.role != Role.OWNER and target.role == Role.OWNER:
                raise PermissionDenied("Only an owner can remove an owner.")
        if target.role == Role.OWNER and self._owner_count(target.organization_id) <= 1:
            raise ValidationError({"detail": ["A workspace must keep at least one owner."]})
        record(
            request,
            "organization.member_removed",
            obj=target,
            organization=target.organization,
            metadata={"user": target.user.email, "self": leaving_self},
        )
        target.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
