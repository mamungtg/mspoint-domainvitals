from django.db.models import Max
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.domains.validation import InvalidDomain, normalize_domain
from apps.domains.views import _domain_for

from .models import DnsChange, DnsScan
from .propagation import RECORD_TYPES, check_propagation
from .services import resolver_for


class ChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DnsChange
        fields = ["id", "name", "rtype", "kind", "old_values", "new_values", "old_ttl", "new_ttl", "detected_at"]


def _latest_inventory(domain):
    return (
        DnsScan.objects.filter(domain=domain, status=DnsScan.Status.COMPLETED)
        .exclude(records={})
        .order_by("-created_at")
        .first()
    )


class DomainRecordsView(APIView):
    @extend_schema(responses={200: dict}, tags=["dns"])
    def get(self, request, domain_id):
        domain, _ = _domain_for(request.user, domain_id)
        scan = _latest_inventory(domain)
        if scan is None:
            return Response({"scanned_at": None, "records": [], "name_servers": []})
        last = {
            (c["name"], c["rtype"]): c["at"]
            for c in DnsChange.objects.filter(domain=domain).values("name", "rtype").annotate(at=Max("detected_at"))
        }
        first_scan = (
            DnsScan.objects.filter(domain=domain, status=DnsScan.Status.COMPLETED)
            .exclude(records={})
            .order_by("created_at")
            .first()
        )
        rows = []
        for key, rs in sorted(scan.records.items(), key=lambda kv: (kv[0].split()[0] != domain.name, kv[0])):
            name, rtype = key.rsplit(" ", 1)
            rows.append(
                {
                    "name": name,
                    "type": rtype,
                    "ttl": rs.get("ttl"),
                    "values": rs.get("values", []),
                    "last_changed": last.get((name, rtype)),
                    "tracked_since": first_scan.created_at if first_scan else None,
                }
            )
        dns_data = (scan.results.get("dns") or {}).get("data", {})
        return Response(
            {
                "scanned_at": scan.completed_at,
                "records": rows,
                "name_servers": dns_data.get("name_servers", []),
                "soa": dns_data.get("soa"),
                "hosts": dns_data.get("hosts", []),
            }
        )


class DomainChangesView(APIView):
    @extend_schema(responses={200: ChangeSerializer(many=True)}, tags=["dns"])
    def get(self, request, domain_id):
        domain, _ = _domain_for(request.user, domain_id)
        qs = DnsChange.objects.filter(domain=domain)
        if request.query_params.get("name"):
            qs = qs.filter(name=request.query_params["name"].lower())
        if request.query_params.get("type"):
            qs = qs.filter(rtype=request.query_params["type"].upper())
        return Response(ChangeSerializer(qs[:200], many=True).data)


class PropagationQuery(serializers.Serializer):
    name = serializers.CharField(max_length=253)
    type = serializers.ChoiceField(choices=RECORD_TYPES)

    def validate_name(self, value):
        try:
            return normalize_domain(value) if not value.startswith("_") else value.strip().rstrip(".").lower()
        except InvalidDomain as exc:
            raise serializers.ValidationError(str(exc)) from exc


class DomainPropagationView(APIView):
    throttle_scope = "tools"

    @extend_schema(parameters=[PropagationQuery], responses={200: dict}, tags=["dns"])
    def get(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        ser = PropagationQuery(data=request.query_params)
        ser.is_valid(raise_exception=True)
        name, rtype = ser.validated_data["name"], ser.validated_data["type"]
        if not (name == domain.name or name.endswith("." + domain.name)):
            raise ValidationError({"name": [f"Use {domain.name} or one of its subdomains."]})
        demo = m.organization.is_demo
        return Response(check_propagation(name, rtype, resolver=resolver_for(domain) if demo else None, live=not demo))


class ToolPropagationView(APIView):
    """Propagation for any public name (Domain checker). Read-only DNS queries."""

    throttle_scope = "tools"

    @extend_schema(request=PropagationQuery, responses={200: dict}, tags=["tools"])
    def post(self, request):
        ser = PropagationQuery(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(check_propagation(ser.validated_data["name"], ser.validated_data["type"]))
