from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.domains.views import _require_write
from apps.organizations.models import MANAGER_ROLES
from apps.organizations.permissions import get_membership_or_404

from .demo import seed_demo_alerts
from .models import Alert, Channel, Delivery
from .notify import deliver_now
from .serializers import AlertSerializer, ChannelSerializer

MAX_CHANNELS = 20


def _require_manager(m):
    _require_write(m, roles=MANAGER_ROLES)


class OrgAlertsView(APIView):
    @extend_schema(
        parameters=[OpenApiParameter("status", str, description="open (default), resolved or notice")],
        responses={200: dict},
        tags=["alerts"],
    )
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        if m.organization.is_demo:
            seed_demo_alerts(m.organization)
        st = request.query_params.get("status", "open")
        if st not in Alert.Status.values:
            raise ValidationError({"status": ["Use open, resolved or notice."]})
        qs = Alert.objects.filter(organization_id=org_id).select_related("domain", "acknowledged_by")
        open_qs = qs.filter(status=Alert.Status.OPEN)
        items = qs.filter(status=st).order_by("-updated_at" if st == "resolved" else "-opened_at")[:200]
        return Response(
            {
                "counts": {
                    "open": open_qs.count(),
                    "critical": open_qs.filter(severity="critical").count(),
                    "unacknowledged": open_qs.filter(acknowledged_at__isnull=True).count(),
                },
                "alerts": AlertSerializer(items, many=True).data,
            }
        )


class AlertAcknowledgeView(APIView):
    @extend_schema(request=None, responses={200: AlertSerializer}, tags=["alerts"])
    def post(self, request, alert_id):
        alert = get_object_or_404(Alert.objects.select_related("domain"), pk=alert_id)
        m = get_membership_or_404(request.user, alert.organization_id)
        _require_write(m)
        if alert.status != Alert.Status.OPEN:
            raise ValidationError({"detail": ["Only open alerts can be acknowledged."]})
        if alert.acknowledged_at is None:
            alert.acknowledged_by, alert.acknowledged_at = request.user, timezone.now()
            alert.save(update_fields=["acknowledged_by", "acknowledged_at", "updated_at"])
            record(
                request, "alert.acknowledged", obj=alert, organization=m.organization, metadata={"title": alert.title}
            )
        return Response(AlertSerializer(alert).data)


class ChannelsView(APIView):
    def get_throttles(self):
        self.throttle_scope = "domain_write" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(responses={200: ChannelSerializer(many=True)}, tags=["alerts"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        data = ChannelSerializer(Channel.objects.filter(organization_id=org_id), many=True).data
        if m.role not in MANAGER_ROLES:  # only managers see webhook signing secrets
            for d in data:
                d["secret"] = None
        return Response(data)

    @extend_schema(request=ChannelSerializer, responses={201: ChannelSerializer}, tags=["alerts"])
    def post(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        _require_manager(m)
        if Channel.objects.filter(organization_id=org_id).count() >= MAX_CHANNELS:
            raise ValidationError({"detail": [f"A workspace can have up to {MAX_CHANNELS} channels."]})
        ser = ChannelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        from apps.billing.limits import check_channel

        check_channel(m.organization, ser.validated_data["type"])
        ch = ser.save(organization=m.organization, created_by=request.user)
        record(
            request,
            "alert_channel.created",
            obj=ch,
            organization=m.organization,
            metadata={"type": ch.type, "name": ch.name},
        )
        return Response(ChannelSerializer(ch).data, status=status.HTTP_201_CREATED)


def _channel_for(request, channel_id):
    ch = get_object_or_404(Channel.objects.select_related("organization"), pk=channel_id)
    m = get_membership_or_404(request.user, ch.organization_id)
    _require_manager(m)
    return ch, m


class ChannelDetailView(APIView):
    @extend_schema(request=ChannelSerializer, responses={200: ChannelSerializer}, tags=["alerts"])
    def patch(self, request, channel_id):
        ch, m = _channel_for(request, channel_id)
        ser = ChannelSerializer(ch, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        record(request, "alert_channel.updated", obj=ch, organization=m.organization, metadata={"name": ch.name})
        return Response(ser.data)

    @extend_schema(responses={204: None}, tags=["alerts"])
    def delete(self, request, channel_id):
        ch, m = _channel_for(request, channel_id)
        record(request, "alert_channel.deleted", obj=ch, organization=m.organization, metadata={"name": ch.name})
        ch.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChannelTestView(APIView):
    throttle_scope = "invite"

    @extend_schema(request=None, responses={200: dict}, tags=["alerts"])
    def post(self, request, channel_id):
        ch, m = _channel_for(request, channel_id)
        if m.organization.is_demo:
            raise PermissionDenied()
        d = deliver_now(Delivery.objects.create(channel=ch, event=Delivery.Event.TEST))
        return Response({"sent": d.status == Delivery.Status.SENT, "error": d.error})
