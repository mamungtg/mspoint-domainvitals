import io
from datetime import timedelta

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.billing.models import BillingAccount
from apps.dns_monitor.models import DnsScan
from apps.domains.models import Domain
from apps.organizations.models import Membership, Role
from apps.reports import data as report_data
from apps.reports.branding import brand_for
from apps.reports.models import ReportBranding, ReportSchedule
from apps.reports.pdf import _latin, render
from apps.reports.tasks import send_monthly_reports

pytestmark = pytest.mark.django_db


def png(w=300, h=100, fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 50, 0)).save(buf, fmt)
    return buf.getvalue()


@pytest.fixture
def org(make_user, make_org):
    return make_org(make_user("owner@acme.com"))


@pytest.fixture
def domain(org):
    d = Domain.objects.create(organization=org, name="acme.com", verified_at=timezone.now())
    now = timezone.now()
    for i, score in enumerate([60, 85]):
        scan = DnsScan.objects.create(
            domain=d,
            status="completed",
            created_at=now - timedelta(days=3 - i),
            completed_at=now,
            health_score=score,
            overall_status="warn",
            summary={"spf": "pass", "dkim": "warn", "dmarc": "pass", "mx": "pass", "dns": "pass"},
            results={
                "dkim": {
                    "findings": [
                        {
                            "severity": "warning",
                            "title": "No DKIM key found",
                            "fix": "Turn on DKIM – with a 2048-bit key",
                        }
                    ]
                }
            },
        )
    d.latest_scan = scan
    d.save()
    return d


def test_report_data(org, domain):
    d = report_data.build(org, None, 30)
    item = d["domains"][0]
    assert d["totals"]["domains"] == 1 and d["totals"]["average_score"] == 85 and d["totals"]["warnings"] == 1
    assert item["findings"][0]["title"] == "No DKIM key found" and [s for _, s in item["trend"]] == [60, 85]
    assert not d["single"] and report_data.build(org, [domain.pk], 30)["single"]


def test_pdf_renders_and_handles_unicode(org, domain):
    org.name = "Ünïcode – Studio বাংলা"
    pdf = render(report_data.build(org, None, 30), brand_for(org))
    assert pdf.startswith(b"%PDF") and len(pdf) > 3000
    assert _latin("17 Oct – 16 Nov “x” …") == '17 Oct - 16 Nov "x" ...'


def test_pdf_endpoint(org, domain, client_for, make_user):
    c = client_for(org.owner)
    r = c.get(f"/api/v1/organizations/{org.id}/reports/pdf/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "domainvitals-report-domains-" in r["Content-Disposition"]
    r = c.get(f"/api/v1/organizations/{org.id}/reports/pdf/?domain={domain.id}&days=90")
    assert r.status_code == 200 and "domainvitals-report-acme.com-" in r["Content-Disposition"]
    assert c.get(f"/api/v1/organizations/{org.id}/reports/pdf/?days=7").status_code == 400
    other = Domain.objects.create(organization=org, name="pending.com")
    assert c.get(f"/api/v1/organizations/{org.id}/reports/pdf/?domain={other.id}").status_code == 400  # not verified
    assert client_for(make_user("out@x.com")).get(f"/api/v1/organizations/{org.id}/reports/pdf/").status_code == 404


def test_demo_workspace_report(make_user, client_for):
    c = client_for(make_user("demo@x.com"))
    org_id = c.post("/api/v1/organizations/demo/").data["id"]
    r = c.get(f"/api/v1/organizations/{org_id}/reports/pdf/")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_branding_and_white_label_gate(org, client_for, make_user):
    c = client_for(org.owner)
    url = f"/api/v1/organizations/{org.id}/reports/branding/"
    r = c.patch(
        url,
        {"company_name": "Acme IT", "accent_color": "#CC3300", "footer_text": "support@acme.example"},
        format="json",
    )
    assert r.status_code == 200 and r.data["white_label"] is True  # trial = Agency
    assert c.patch(url, {"accent_color": "red"}, format="json").status_code == 400
    assert brand_for(org).name == "Acme IT"
    BillingAccount.objects.filter(organization=org).update(plan="starter", status="active", trial_ends_at=None)
    fresh = type(org).objects.get(pk=org.pk)
    assert brand_for(fresh).name == "DomainVitals by MSPoint"  # Starter: no white-label
    member = make_user("m@acme.com")
    Membership.objects.create(organization=org, user=member, role=Role.MEMBER)
    assert client_for(member).patch(url, {"company_name": "x"}, format="json").status_code == 403
    assert client_for(member).get(url).data["company_name"] == "Acme IT"


def test_logo_upload(org, client_for):
    c = client_for(org.owner)
    url = f"/api/v1/organizations/{org.id}/reports/branding/logo/"
    r = c.post(url, {"file": SimpleUploadedFile("logo.jpg", png(1200, 600, "JPEG"))}, format="multipart")
    assert r.status_code == 200 and r.data["has_logo"]
    stored = Image.open(io.BytesIO(bytes(ReportBranding.objects.get(organization=org).logo)))
    assert stored.format == "PNG" and stored.size[0] <= 600 and stored.size[1] <= 200
    assert c.get(url)["Content-Type"] == "image/png"
    r = c.post(url, {"file": SimpleUploadedFile("x.gif", png(fmt="GIF"))}, format="multipart")
    assert r.status_code == 400 and "PNG or JPEG" in str(r.data)
    r = c.post(url, {"file": SimpleUploadedFile("x.png", b"<svg onload=alert(1)>")}, format="multipart")
    assert r.status_code == 400
    assert c.delete(url).data["has_logo"] is False
    assert render(report_data.build(org, None, 30), brand_for(org)).startswith(b"%PDF")


def test_monthly_schedule(org, domain, client_for):
    c = client_for(org.owner)
    url = f"/api/v1/organizations/{org.id}/reports/schedule/"
    assert c.put(url, {"enabled": True, "recipients": []}, format="json").status_code == 400
    assert c.put(url, {"enabled": True, "recipients": ["nope"]}, format="json").status_code == 400
    r = c.put(url, {"enabled": True, "recipients": ["Client@Example.com"]}, format="json")
    assert r.status_code == 200 and r.data["recipients"] == ["client@example.com"]
    send_monthly_reports()
    send_monthly_reports()  # once per month
    reports = [m for m in mail.outbox if m.to == ["client@example.com"]]
    assert len(reports) == 1 and reports[0].attachments[0][2] == "application/pdf"
    assert reports[0].attachments[0][1].startswith(b"%PDF")
    assert ReportSchedule.objects.get(organization=org).last_sent_on == timezone.now().date()
