from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.domains.views import _require_write
from apps.organizations.models import MANAGER_ROLES
from apps.organizations.permissions import get_membership_or_404

from . import data as report_data
from .branding import LogoError, brand_for, process_logo, white_label_allowed
from .models import ReportBranding, ReportSchedule
from .pdf import filename, render

PERIODS = (30, 90)


def _manager(request, org_id):
    m = get_membership_or_404(request.user, org_id)
    if m.organization.is_demo:
        raise PermissionDenied("The sample workspace can't be changed.")
    _require_write(m, roles=MANAGER_ROLES)
    return m


class ReportPdfView(APIView):
    throttle_scope = "reports"

    @extend_schema(
        parameters=[
            OpenApiParameter("domain", str, description="Domain id; omit for every verified domain"),
            OpenApiParameter("days", int, description="30 (default) or 90"),
        ],
        responses={(200, "application/pdf"): bytes},
        tags=["reports"],
    )
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        org = m.organization
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 30
        if days not in PERIODS:
            raise ValidationError({"days": ["Use 30 or 90."]})
        domain_id = request.query_params.get("domain")
        if domain_id and not org.domains.filter(pk=domain_id, verified_at__isnull=False).exists():
            raise ValidationError({"domain": ["Choose a verified domain in this workspace."]})
        data = report_data.build(org, [domain_id] if domain_id else None, days)
        pdf = render(data, brand_for(org))
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename(data)}"'
        resp["Cache-Control"] = "no-store"
        return resp


class BrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportBranding
        fields = ["company_name", "accent_color", "footer_text"]


def _branding_payload(org, b):
    return {
        "company_name": b.company_name if b else "",
        "accent_color": b.accent_color if b else "#14508F",
        "footer_text": b.footer_text if b else "",
        "has_logo": bool(b and b.logo),
        "white_label": white_label_allowed(org),
    }


class BrandingView(APIView):
    @extend_schema(responses={200: dict}, tags=["reports"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        return Response(
            _branding_payload(m.organization, ReportBranding.objects.filter(organization=m.organization).first())
        )

    @extend_schema(request=BrandingSerializer, responses={200: dict}, tags=["reports"])
    def patch(self, request, org_id):
        m = _manager(request, org_id)
        b, _ = ReportBranding.objects.get_or_create(organization=m.organization)
        ser = BrandingSerializer(b, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        record(request, "reports.branding_updated", obj=m.organization, organization=m.organization)
        return Response(_branding_payload(m.organization, b))


class LogoView(APIView):
    parser_classes = [MultiPartParser]
    throttle_scope = "domain_write"

    @extend_schema(responses={(200, "image/png"): bytes}, tags=["reports"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        b = ReportBranding.objects.filter(organization=m.organization).first()
        if not b or not b.logo:
            return Response(status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(bytes(b.logo), content_type="image/png")
        resp["Cache-Control"] = "private, no-cache"
        resp["X-Content-Type-Options"] = "nosniff"
        return resp

    @extend_schema(
        request={
            "multipart/form-data": {"type": "object", "properties": {"file": {"type": "string", "format": "binary"}}}
        },
        responses={200: dict},
        tags=["reports"],
    )
    def post(self, request, org_id):
        m = _manager(request, org_id)
        f = request.FILES.get("file")
        if f is None:
            raise ValidationError({"file": ["Choose a PNG or JPEG image."]})
        try:
            png = process_logo(f.read(1024 * 1024 + 1))
        except LogoError as e:
            raise ValidationError({"file": [str(e)]}) from None
        b, _ = ReportBranding.objects.get_or_create(organization=m.organization)
        b.logo = png
        b.save(update_fields=["logo", "updated_at"])
        record(request, "reports.logo_uploaded", obj=m.organization, organization=m.organization)
        return Response(_branding_payload(m.organization, b))

    @extend_schema(responses={200: dict}, tags=["reports"])
    def delete(self, request, org_id):
        m = _manager(request, org_id)
        b = ReportBranding.objects.filter(organization=m.organization).first()
        if b:
            b.logo = None
            b.save(update_fields=["logo", "updated_at"])
        return Response(_branding_payload(m.organization, b))


class ScheduleSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    recipients = serializers.ListField(child=serializers.CharField(max_length=254), max_length=10)

    def validate_recipients(self, value):
        out = []
        for v in value:
            v = v.strip().lower()
            try:
                validate_email(v)
            except DjangoValidationError:
                raise serializers.ValidationError(f"{v} is not a valid email address.") from None
            out.append(v)
        return sorted(set(out))

    def validate(self, attrs):
        if attrs["enabled"] and not attrs["recipients"]:
            raise serializers.ValidationError({"recipients": ["Add at least one address."]})
        return attrs


class ScheduleView(APIView):
    @extend_schema(responses={200: dict}, tags=["reports"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        sch = ReportSchedule.objects.filter(organization=m.organization).first()
        return Response(
            {
                "enabled": bool(sch and sch.enabled),
                "recipients": sch.recipients if sch else [],
                "last_sent_on": sch.last_sent_on.isoformat() if sch and sch.last_sent_on else None,
            }
        )

    @extend_schema(request=ScheduleSerializer, responses={200: dict}, tags=["reports"])
    def put(self, request, org_id):
        m = _manager(request, org_id)
        ser = ScheduleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sch, _ = ReportSchedule.objects.get_or_create(organization=m.organization)
        sch.enabled, sch.recipients = ser.validated_data["enabled"], ser.validated_data["recipients"]
        sch.save()
        record(
            request,
            "reports.schedule_updated",
            obj=m.organization,
            organization=m.organization,
            metadata={"enabled": sch.enabled, "recipients": len(sch.recipients)},
        )
        return Response(
            {
                "enabled": sch.enabled,
                "recipients": sch.recipients,
                "last_sent_on": sch.last_sent_on.isoformat() if sch.last_sent_on else None,
            }
        )
