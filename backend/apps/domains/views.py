from collections import Counter, defaultdict
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
from apps.dns_monitor.checks import CHECK_ORDER, run_checks, verify_ownership
from apps.dns_monitor.checks.dkim import check_dkim
from apps.dns_monitor.checks.dmarc import check_dmarc
from apps.dns_monitor.checks.infra import check_infra
from apps.dns_monitor.checks.mx import check_mx
from apps.dns_monitor.checks.spf import check_spf
from apps.dns_monitor.models import DnsScan
from apps.dns_monitor.resolver import LiveResolver
from apps.dns_monitor.services import active_scan, queue_scan, resolver_for
from apps.organizations.models import MANAGER_ROLES, Role
from apps.organizations.permissions import get_membership_or_404
from apps.organizations.serializers import OrganizationSerializer

from . import serializers as s
from .demo import ensure_demo_workspace
from .models import Domain

WRITE_ROLES = {Role.OWNER, Role.ADMIN, Role.MEMBER}
DEMO_MSG = "This is a sample workspace and cannot be changed. Create your own workspace to add domains."


def _require_write(membership, roles=WRITE_ROLES):
    if membership.organization.is_demo:
        raise PermissionDenied(DEMO_MSG)
    if membership.role not in roles:
        raise PermissionDenied("Your role does not allow this.")


def _domain_for(user, domain_id):
    """Load a domain the user can see; outsiders get 404."""
    domain = get_object_or_404(Domain.objects.select_related("organization", "latest_scan"), pk=domain_id)
    membership = get_membership_or_404(user, domain.organization_id)
    return domain, membership


class OrgDomainsView(APIView):
    def get_throttles(self):
        self.throttle_scope = "domain_write" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(responses={200: s.DomainSerializer(many=True)}, tags=["domains"])
    def get(self, request, org_id):
        get_membership_or_404(request.user, org_id)
        qs = Domain.objects.filter(organization_id=org_id).select_related("latest_scan").order_by("name")
        return Response(s.DomainSerializer(qs, many=True).data)

    @extend_schema(request=s.AddDomainSerializer, responses={201: s.DomainSerializer}, tags=["domains"])
    def post(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        _require_write(m)
        if not request.user.email_verified:
            raise PermissionDenied("Confirm your email address before adding domains.")
        ser = s.AddDomainSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if Domain.objects.filter(organization_id=org_id).count() >= settings.DOMAIN_LIMIT_PER_ORG:
            raise ValidationError(
                {"name": [f"This workspace already has the maximum of {settings.DOMAIN_LIMIT_PER_ORG} domains."]}
            )
        try:
            with transaction.atomic():
                domain = Domain.objects.create(
                    organization=m.organization, name=ser.validated_data["name"], added_by=request.user
                )
        except IntegrityError:
            raise ValidationError({"name": ["This domain is already in this workspace."]}) from None
        record(request, "domain.added", obj=domain, organization=m.organization, metadata={"domain": domain.name})
        return Response(s.DomainSerializer(domain).data, status=status.HTTP_201_CREATED)


class DomainDetailView(APIView):
    @extend_schema(responses={200: s.DomainSerializer}, tags=["domains"])
    def get(self, request, domain_id):
        domain, _ = _domain_for(request.user, domain_id)
        return Response(s.DomainSerializer(domain).data)

    @extend_schema(request=s.DomainSerializer, responses={200: s.DomainSerializer}, tags=["domains"])
    def patch(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        _require_write(m)
        ser = s.DomainSerializer(
            domain,
            data={
                k: v
                for k, v in request.data.items()
                if k in ("monitoring_enabled", "dkim_selectors", "dns_watch_names")
            },
            partial=True,
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        record(
            request,
            "domain.updated",
            obj=domain,
            organization=domain.organization,
            metadata={"fields": sorted(ser.validated_data)},
        )
        return Response(s.DomainSerializer(domain).data)

    @extend_schema(responses={204: None}, tags=["domains"])
    def delete(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        _require_write(m, MANAGER_ROLES)
        record(
            request, "domain.removed", obj=domain, organization=domain.organization, metadata={"domain": domain.name}
        )
        domain.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _recent_changes(org_id, limit=8):
    from apps.dns_monitor.models import DnsChange

    rows = DnsChange.objects.filter(domain__organization_id=org_id).select_related("domain")[:limit]
    return [
        {
            "id": str(c.id),
            "domain_id": str(c.domain_id),
            "domain": c.domain.name,
            "name": c.name,
            "rtype": c.rtype,
            "kind": c.kind,
            "old_values": c.old_values,
            "new_values": c.new_values,
            "old_ttl": c.old_ttl,
            "new_ttl": c.new_ttl,
            "detected_at": c.detected_at.isoformat(),
        }
        for c in rows
    ]


def _tls_summary(org):
    from apps.ssl_monitor.demo import seed_demo_tls
    from apps.ssl_monitor.reports import certificate_rows, summarize

    if org.is_demo:
        seed_demo_tls(org)
    rows = certificate_rows(org.id)
    soonest = sorted((r for r in rows if r["days_left"] is not None), key=lambda r: r["days_left"])[:5]
    return {**summarize(rows), "soonest": soonest}


def _start_tls_monitoring(domain):
    """Check the certificates for example.com and www.example.com right away."""
    from apps.ssl_monitor.services import ensure_default_hosts, queue
    from apps.ssl_monitor.tasks import scan_tls_host

    ensure_default_hosts(domain)
    for host in domain.tls_hosts.all():
        scan = queue(host, "verification")
        transaction.on_commit(lambda sid=str(scan.pk): scan_tls_host.delay(sid))


class DomainVerifyView(APIView):
    throttle_scope = "domain_write"

    @extend_schema(request=None, responses={200: s.DomainSerializer}, tags=["domains"])
    def post(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        _require_write(m)
        if domain.is_verified:
            return Response(s.DomainSerializer(domain).data)
        if not verify_ownership(domain.name, domain.verification_token, LiveResolver()):
            raise ValidationError(
                {
                    "verification": [
                        f"The TXT record was not found at {domain.verification_host}. DNS changes can take a few minutes "
                        "to appear; check the host name and value, then try again."
                    ]
                }
            )
        domain.mark_verified()
        domain.save(update_fields=["verified_at", "verification_checked_at", "verification_failing_since"])
        record(
            request, "domain.verified", obj=domain, organization=domain.organization, metadata={"domain": domain.name}
        )
        queue_scan(domain, DnsScan.Trigger.VERIFICATION)
        _start_tls_monitoring(domain)
        return Response(s.DomainSerializer(domain).data)


class DomainScanView(APIView):
    @extend_schema(request=None, responses={202: s.ScanSummarySerializer}, tags=["domains"])
    def post(self, request, domain_id):
        domain, m = _domain_for(request.user, domain_id)
        _require_write(m)
        if not domain.is_verified:
            raise PermissionDenied("Verify that you control this domain before scanning it.")
        running = active_scan(domain)
        if running:
            return Response(s.ScanSummarySerializer(running).data, status=status.HTTP_202_ACCEPTED)
        last = domain.scans.filter(trigger=DnsScan.Trigger.MANUAL).first()
        cooldown = settings.DNS_MANUAL_SCAN_COOLDOWN_SECONDS
        if last and (timezone.now() - last.created_at).total_seconds() < cooldown:
            raise Throttled(wait=cooldown - (timezone.now() - last.created_at).total_seconds())
        scan = queue_scan(domain, DnsScan.Trigger.MANUAL)
        record(request, "domain.scan_requested", obj=domain, organization=domain.organization)
        return Response(s.ScanSummarySerializer(scan).data, status=status.HTTP_202_ACCEPTED)


class DomainScansView(APIView):
    @extend_schema(responses={200: s.ScanSummarySerializer(many=True)}, tags=["domains"])
    def get(self, request, domain_id):
        domain, _ = _domain_for(request.user, domain_id)
        return Response(s.ScanSummarySerializer(domain.scans.all()[:30], many=True).data)


class ScanDetailView(APIView):
    @extend_schema(responses={200: s.ScanDetailSerializer}, tags=["domains"])
    def get(self, request, scan_id):
        scan = get_object_or_404(DnsScan.objects.select_related("domain"), pk=scan_id)
        get_membership_or_404(request.user, scan.domain.organization_id)
        return Response(s.ScanDetailSerializer(scan).data)


class OverviewView(APIView):
    """Workspace KPIs and chart data, computed from the latest scans."""

    @extend_schema(responses={200: dict}, tags=["domains"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        domains = list(Domain.objects.filter(organization_id=org_id).select_related("latest_scan"))
        scanned = [d for d in domains if d.latest_scan and d.latest_scan.status == DnsScan.Status.COMPLETED]
        status_count = Counter(d.latest_scan.overall_status for d in scanned)
        policies = Counter()
        check_status = {c: Counter() for c in CHECK_ORDER}
        attention, findings = [], []
        for d in scanned:
            sc = d.latest_scan
            pol = ((sc.results.get("dmarc") or {}).get("data") or {}).get("policy")
            policies[pol or "missing"] += 1
            for c in check_status:
                check_status[c][sc.summary.get(c, "unknown")] += 1
            top = None
            for c in CHECK_ORDER:
                for f in (sc.results.get(c) or {}).get("findings", []):
                    if f["severity"] in ("critical", "warning"):
                        findings.append({"domain_id": str(d.pk), "domain": d.name, "check": c, **f})
                        if top is None or (f["severity"] == "critical" and top["severity"] != "critical"):
                            top = f
            if sc.overall_status in ("fail", "warn"):
                attention.append(
                    {
                        "domain_id": str(d.pk),
                        "domain": d.name,
                        "score": sc.health_score,
                        "status": sc.overall_status,
                        "top_finding": top["title"] if top else None,
                    }
                )
        attention.sort(key=lambda a: a["score"] if a["score"] is not None else 101)
        findings.sort(key=lambda f: (f["severity"] != "critical", f["domain"]))

        # 14-day average health score, one point per day (latest scan per domain per day)
        # Window = the last 14 calendar days (UTC), starting at midnight.
        since = (timezone.now() - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_scores: dict = defaultdict(dict)
        for sc in DnsScan.objects.filter(
            domain__organization_id=org_id,
            status=DnsScan.Status.COMPLETED,
            created_at__gte=since.replace(hour=0, minute=0),
        ).order_by("created_at"):
            day_scores[sc.created_at.date()][sc.domain_id] = sc.health_score
        trend = []
        for i in range(13, -1, -1):
            day = (timezone.now() - timedelta(days=i)).date()
            vals = list(day_scores.get(day, {}).values())
            trend.append({"date": day.isoformat(), "score": round(sum(vals) / len(vals)) if vals else None})

        scores = [d.latest_scan.health_score for d in scanned if d.latest_scan.health_score is not None]
        return Response(
            {
                "domains": {
                    "total": len(domains),
                    "verified": sum(1 for d in domains if d.is_verified),
                    "unverified": sum(1 for d in domains if not d.is_verified),
                    "scanned": len(scanned),
                },
                "health": {
                    "pass": status_count.get("pass", 0),
                    "warn": status_count.get("warn", 0),
                    "fail": status_count.get("fail", 0),
                    "error": status_count.get("error", 0),
                    "average_score": round(sum(scores) / len(scores)) if scores else None,
                },
                "issues": {
                    "critical": sum(d.latest_scan.critical_count for d in scanned),
                    "warning": sum(d.latest_scan.warning_count for d in scanned),
                },
                "dmarc_policies": {k: policies.get(k, 0) for k in ("reject", "quarantine", "none", "missing")},
                "checks": {c: dict(v) for c, v in check_status.items()},
                "score_trend": trend,
                "attention": attention[:6],
                "findings": findings[:10],
                "tls": _tls_summary(m.organization),
                "recent_changes": _recent_changes(org_id),
            }
        )


class ToolCheckView(APIView):
    """Instant lookup for any domain (public DNS only; nothing is stored)."""

    throttle_scope = "tools"

    @extend_schema(request=s.ToolCheckSerializer, responses={200: dict}, tags=["tools"])
    def post(self, request):
        ser = s.ToolCheckSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        name, check = ser.validated_data["domain"], ser.validated_data["check"]
        selectors = [ser.validated_data["selector"]] if ser.validated_data.get("selector") else []
        resolver = LiveResolver()
        if check == "all":
            out = run_checks(name, resolver, selectors)
            out["results"].get("dns", {}).get("data", {}).pop("records", None)
            return Response({"domain": name, **out})
        if check == "dkim":
            result = check_dkim(name, resolver, selectors)
        elif check == "dns":
            result = check_infra(name, resolver, hosts=[f"www.{name}"], dkim_selectors=[])
        else:
            result = {"spf": check_spf, "dmarc": check_dmarc, "mx": check_mx}[check](name, resolver)
        body = result.to_dict()
        body.get("data", {}).pop("records", None)
        return Response({"domain": name, "results": {check: body}, "summary": {check: result.status}})


class DemoWorkspaceView(APIView):
    @extend_schema(request=None, responses={200: OrganizationSerializer}, tags=["organizations"])
    def post(self, request):
        org = ensure_demo_workspace(request.user)
        return Response(OrganizationSerializer(org, context={"roles": {org.pk: Role.VIEWER}}).data)


_ = resolver_for  # re-exported for tests
