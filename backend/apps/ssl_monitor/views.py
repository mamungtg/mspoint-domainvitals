from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, Throttled, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.domains.views import _domain_for, _require_write
from apps.organizations.permissions import get_membership_or_404

from . import serializers as s
from .demo import seed_demo_tls
from .models import MonitoredHost
from .reports import certificate_rows, summarize
from .services import active_scan, in_scope, queue
from .tasks import scan_tls_host

MAX_HOSTS_PER_DOMAIN = 20


def _host_for(user, host_id):
    host = get_object_or_404(MonitoredHost.objects.select_related("domain", "domain__organization"), pk=host_id)
    membership = get_membership_or_404(user, host.domain.organization_id)
    return host, membership


def _bootstrap(domains):
    """Verified domains that predate SSL monitoring (or lost their hosts) get
    apex + www right away instead of waiting for the scheduler."""
    from .services import ensure_default_hosts

    for d in domains:
        if d.is_verified and not d.organization.is_demo and not d.tls_hosts.exists():
            ensure_default_hosts(d)
            for host in d.tls_hosts.all():
                _queue_now(host, "verification")


def _queue_now(host, trigger):
    scan = queue(host, trigger)
    transaction.on_commit(lambda: scan_tls_host.delay(str(scan.pk)))
    return scan


class OrgCertificatesView(APIView):
    @extend_schema(responses={200: dict}, tags=["ssl"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        if m.organization.is_demo:
            seed_demo_tls(m.organization)
        else:
            _bootstrap(m.organization.domains.filter(verified_at__isnull=False).select_related("organization"))
        rows = certificate_rows(org_id)
        return Response({"summary": summarize(rows), "certificates": rows})


class DomainHostsView(APIView):
    @extend_schema(responses={200: dict}, tags=["ssl"])
    def get(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        if m.organization.is_demo:
            seed_demo_tls(m.organization)
        else:
            _bootstrap([domain])
        rows = [r for r in certificate_rows(domain.organization_id) if r["domain_id"] == str(domain.id)]
        return Response(rows)

    @extend_schema(request=s.AddHostSerializer, responses={201: dict}, tags=["ssl"])
    def post(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        _require_write(m)
        if not domain.is_verified:
            raise PermissionDenied("Verify this domain before adding host names to check.")
        ser = s.AddHostSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        hostname, port = ser.validated_data["hostname"], ser.validated_data["port"]
        if not in_scope(hostname, domain.name):
            raise ValidationError(
                {"hostname": [f"Use {domain.name} or one of its subdomains, such as mail.{domain.name}."]}
            )
        if domain.tls_hosts.count() >= MAX_HOSTS_PER_DOMAIN:
            raise ValidationError({"hostname": [f"A domain can have up to {MAX_HOSTS_PER_DOMAIN} host names."]})
        try:
            with transaction.atomic():
                host = MonitoredHost.objects.create(domain=domain, hostname=hostname, port=port)
        except IntegrityError:
            raise ValidationError({"hostname": ["This host name is already being checked."]}) from None
        _queue_now(host, "manual")
        record(request, "tls_host.added", obj=host, organization=domain.organization, metadata={"host": host.label})
        return Response({"id": str(host.id), "label": host.label}, status=status.HTTP_201_CREATED)


class HostDetailView(APIView):
    @extend_schema(responses={204: None}, tags=["ssl"])
    def delete(self, request, host_id):
        host, m = _host_for(request.user, host_id)
        _require_write(m)
        record(request, "tls_host.removed", obj=host, organization=m.organization, metadata={"host": host.label})
        host.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HostScanView(APIView):
    @extend_schema(request=None, responses={202: dict}, tags=["ssl"])
    def post(self, request, host_id):
        host, m = _host_for(request.user, host_id)
        _require_write(m)
        if not host.domain.is_verified:
            raise PermissionDenied("Verify this domain first.")
        if active_scan(host):
            raise ValidationError({"detail": ["A check is already running for this host."]})
        cooldown = getattr(settings, "DNS_MANUAL_SCAN_COOLDOWN_SECONDS", 60)
        last = host.latest_scan
        if last and last.created_at > timezone.now() - timedelta(seconds=cooldown):
            wait = cooldown - (timezone.now() - last.created_at).total_seconds()
            raise Throttled(wait=max(1, int(wait)))
        scan = _queue_now(host, "manual")
        return Response({"id": str(scan.id), "status": scan.status}, status=status.HTTP_202_ACCEPTED)


class HostScansView(APIView):
    @extend_schema(responses={200: s.HostScanSerializer(many=True)}, tags=["ssl"])
    def get(self, request, host_id):
        host, _ = _host_for(request.user, host_id)
        return Response(s.HostScanSerializer(host.scans.all()[:20], many=True).data)
