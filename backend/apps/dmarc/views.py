from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.domains.views import _domain_for, _require_write
from apps.organizations.permissions import get_membership_or_404

from .demo import seed_demo_dmarc
from .parser import MAX_INPUT
from .reports import domain_rows, recent_reports, rua_address, summarize
from .services import ingest_bytes
from .tasks import identify_sources

PERIODS = (7, 30, 90)
DAYS_PARAM = OpenApiParameter("days", int, description="7, 30 or 90 (default 30)")


def _days(request) -> int:
    try:
        days = int(request.query_params.get("days", 30))
    except ValueError:
        days = 30
    if days not in PERIODS:
        raise ValidationError({"days": ["Use 7, 30 or 90."]})
    return days


class OrgDmarcView(APIView):
    @extend_schema(parameters=[DAYS_PARAM], responses={200: dict}, tags=["dmarc"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        if m.organization.is_demo:
            seed_demo_dmarc()
        days = _days(request)
        domains = list(
            m.organization.domains.filter(verified_at__isnull=False).select_related("latest_scan").order_by("name")
        )
        data = summarize([d.name for d in domains], days)
        rows = domain_rows(domains, data["since"])
        return Response({**data, "rua_address": rua_address(), "domains": rows})


class DomainDmarcView(APIView):
    @extend_schema(parameters=[DAYS_PARAM], responses={200: dict}, tags=["dmarc"])
    def get(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        if m.organization.is_demo:
            seed_demo_dmarc()
        days = _days(request)
        if not domain.is_verified:
            return Response({"verified": False, "rua_address": rua_address()})
        data = summarize([domain.name], days)
        return Response(
            {
                **data,
                "verified": True,
                "rua_address": rua_address(),
                "domain": domain_rows([domain], data["since"])[0],
                "reports": recent_reports(domain.name),
            }
        )


class DmarcUploadView(APIView):
    """Upload a report file by hand (useful before the rua= address is set up,
    or to import reports from another service)."""

    parser_classes = [MultiPartParser]
    throttle_scope = "domain_write"

    @extend_schema(
        request={
            "multipart/form-data": {"type": "object", "properties": {"file": {"type": "string", "format": "binary"}}}
        },
        responses={201: dict},
        tags=["dmarc"],
    )
    def post(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        _require_write(m)
        if not domain.is_verified:
            raise PermissionDenied("Verify this domain before importing reports.")
        f = request.FILES.get("file")
        if f is None:
            raise ValidationError({"file": ["Choose a report file (.xml, .gz or .zip)."]})
        if f.size > MAX_INPUT:
            raise ValidationError({"file": ["The file is larger than 10 MB."]})
        result = ingest_bytes(f.read(), source="upload", only_domain=domain.name)
        if result.errors and not result.stored and not result.duplicates:
            raise ValidationError({"file": result.errors[:1]})
        if result.reports:
            identify_sources.delay([str(r.pk) for r in result.reports])
            record(
                request,
                "dmarc.report_uploaded",
                obj=domain,
                organization=domain.organization,
                metadata={"reports": result.stored},
            )
        return Response(
            {"stored": result.stored, "duplicates": result.duplicates}, status=201 if result.stored else 200
        )
