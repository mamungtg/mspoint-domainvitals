import gzip
import io
import zipfile
from datetime import timedelta
from email.message import EmailMessage

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.dmarc import parser, sources
from apps.dmarc.models import DmarcRecord, DmarcReport, SourceIp
from apps.dmarc.parser import ReportError, extract_documents, parse_file, parse_report
from apps.dmarc.reports import reporting_status, suggested_record, summarize
from apps.dmarc.services import attachments, ingest_bytes, ingest_message, poll_mailbox
from apps.dns_monitor.models import DnsScan
from apps.domains.models import Domain
from apps.organizations.models import Membership, Role


@pytest.fixture(autouse=True)
def no_reverse_dns(monkeypatch):
    monkeypatch.setattr(
        sources, "reverse_name", lambda ip, timeout=2.0: "mail-x.google.com" if ip.startswith("209.85.") else ""
    )


def report_xml(domain="acme.com", report_id="r1", begin=None, rows=None, ns=""):
    begin = begin or int((timezone.now() - timedelta(days=1)).timestamp())
    rows = rows or [("209.85.220.41", 120, "pass", "pass", "none"), ("203.0.113.9", 7, "fail", "fail", "reject")]
    recs = "".join(
        f"""<record><row><source_ip>{ip}</source_ip><count>{n}</count>
        <policy_evaluated><disposition>{disp}</disposition><dkim>{dk}</dkim><spf>{sp}</spf></policy_evaluated></row>
        <identifiers><header_from>{domain}</header_from><envelope_from>{domain}</envelope_from></identifiers>
        <auth_results><dkim><domain>{domain}</domain><selector>google</selector><result>{dk}</result></dkim>
        <spf><domain>{domain}</domain><result>{sp}</result></spf></auth_results></record>"""
        for ip, n, dk, sp, disp in rows
    )
    xmlns = f' xmlns="{ns}"' if ns else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feedback{xmlns}><report_metadata><org_name>google.com</org_name><email>noreply-dmarc-support@google.com</email>
<report_id>{report_id}</report_id><date_range><begin>{begin}</begin><end>{begin + 86399}</end></date_range></report_metadata>
<policy_published><domain>{domain}</domain><adkim>r</adkim><aspf>r</aspf><p>reject</p><sp>reject</sp><pct>100</pct></policy_published>
{recs}</feedback>""".encode()


def gz(data):
    return gzip.compress(data)


def zipped(*docs):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, d in enumerate(docs):
            z.writestr(f"report{i}.xml", d)
    return buf.getvalue()


@pytest.fixture
def domain(make_user, make_org):
    owner = make_user("owner@acme.com")
    org = make_org(owner)
    return Domain.objects.create(organization=org, name="acme.com", verified_at=timezone.now())


# --- parser --------------------------------------------------------------------


class TestParser:
    def test_plain_xml(self):
        r = parse_report(report_xml())
        assert r.reporter == "google.com" and r.domain == "acme.com" and r.policy["p"] == "reject"
        assert r.message_count == 127
        good, bad = r.records
        assert good.dkim_aligned and good.spf_aligned and good.dkim[0]["selector"] == "google"
        assert not bad.dkim_aligned and bad.disposition == "reject"

    def test_dmarc2_namespace(self):
        r = parse_report(report_xml(ns="urn:ietf:params:xml:ns:dmarc-2.0"))
        assert r.domain == "acme.com" and len(r.records) == 2

    def test_gzip_and_zip(self):
        assert parse_file(gz(report_xml()))[0].report_id == "r1"
        docs = parse_file(zipped(report_xml(report_id="a"), report_xml(report_id="b")))
        assert [d.report_id for d in docs] == ["a", "b"]

    def test_entity_expansion_rejected(self):
        bomb = (
            b"""<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><feedback>&b;</feedback>"""
        )
        with pytest.raises(ReportError, match="not allowed"):
            parse_report(bomb)

    def test_external_entity_rejected(self):
        xxe = b"""<?xml version="1.0"?><!DOCTYPE f [<!ENTITY x SYSTEM "file:///etc/passwd">]><feedback>&x;</feedback>"""
        with pytest.raises(ReportError):
            parse_report(xxe)

    def test_decompression_limit(self, monkeypatch):
        monkeypatch.setattr(parser, "MAX_XML", 1000)
        with pytest.raises(ReportError, match="25 MB"):
            extract_documents(gz(b"<feedback>" + b" " * 5000 + b"</feedback>"))
        with pytest.raises(ReportError, match="25 MB"):
            extract_documents(zipped(b"<feedback>" + b" " * 5000 + b"</feedback>"))

    def test_too_many_zip_members(self):
        with pytest.raises(ReportError, match="one report"):
            extract_documents(zipped(*[report_xml(report_id=str(i)) for i in range(11)]))

    @pytest.mark.parametrize(
        "data,msg",
        [
            (b"\x00\x01binary", "not an XML"),
            (b"<html></html>", "not a DMARC"),
            (b"<feedback><report_metadata/></feedback>", "sender or report ID"),
            (b"\x1f\x8bnotgzip", "damaged"),
        ],
    )
    def test_rejects_garbage(self, data, msg):
        with pytest.raises(ReportError, match=msg):
            parse_file(data)

    def test_bad_ip_and_period(self):
        with pytest.raises(ReportError, match="IP address"):
            parse_report(report_xml(rows=[("not-an-ip", 1, "pass", "pass", "none")]))
        begin = int(timezone.now().timestamp())
        long_period = report_xml(begin=begin).replace(
            f"<end>{begin + 86399}".encode(), f"<end>{begin + 40 * 86400}".encode()
        )
        with pytest.raises(ReportError, match="period"):
            parse_report(long_period)
        with pytest.raises(ReportError, match="end date"):
            parse_report(report_xml(begin=begin).replace(f"<end>{begin + 86399}".encode(), b"<end>99999999999"))


# --- storing -------------------------------------------------------------------


@pytest.mark.django_db
class TestIngest:
    def test_stores_reports_for_monitored_domains_only(self, domain):
        r = ingest_bytes(gz(report_xml()))
        assert r.stored == 1 and DmarcRecord.objects.filter(domain_name="acme.com").count() == 2
        assert ingest_bytes(gz(report_xml())).duplicates == 1
        assert ingest_bytes(report_xml(domain="stranger.com")).unknown_domain == 1
        assert not DmarcReport.objects.filter(domain_name="stranger.com").exists()

    def test_unverified_domain_is_not_monitored(self, domain):
        Domain.objects.filter(pk=domain.pk).update(verified_at=None)
        assert ingest_bytes(report_xml()).unknown_domain == 1

    def test_upload_must_match_domain(self, domain):
        r = ingest_bytes(report_xml(domain="other.com"), source="upload", only_domain="acme.com")
        assert r.stored == 0 and "not acme.com" in r.errors[0]

    def test_email_attachment(self, domain):
        msg = EmailMessage()
        msg["Subject"] = "Report domain: acme.com"
        msg.set_content("See attachment")
        msg.add_attachment(
            gz(report_xml()), maintype="application", subtype="gzip", filename="google.com!acme.com.xml.gz"
        )
        raw = msg.as_bytes()
        assert len(attachments(raw)) == 1
        assert ingest_message(raw).stored == 1

    def test_poll_mailbox_marks_messages_read(self, domain, settings):
        msg = EmailMessage()
        msg.set_content("x")
        msg.add_attachment(zipped(report_xml()), maintype="application", subtype="zip", filename="r.zip")
        raw = msg.as_bytes()

        class FakeImap:
            flagged = []

            def select(self, folder):
                return "OK", [b"1"]

            def search(self, charset, crit):
                return "OK", [b"1 2"]

            def fetch(self, num, what):
                if what == "(RFC822.SIZE)":
                    size = len(raw) if num == b"1" else 50_000_000
                    return "OK", [f"{num.decode()} (RFC822.SIZE {size})".encode()]
                return "OK", [(b"1 (BODY[] {n}", raw)]

            def store(self, num, op, flag):
                self.flagged.append(num)

            def logout(self):
                pass

            def login(self, *a):
                pass

        imap = FakeImap()
        res = poll_mailbox(connect=lambda: imap)
        assert res.stored == 1 and imap.flagged == [b"1", b"2"]


# --- reporting -----------------------------------------------------------------


@pytest.mark.django_db
class TestReports:
    def test_summary_groups_senders(self, domain):
        ingest_bytes(report_xml())
        sources.identify(["209.85.220.41", "203.0.113.9"])
        s = summarize(["acme.com"], 30)
        t = s["totals"]
        assert t["messages"] == 127 and t["passed"] == 120 and t["rejected"] == 7
        assert t["unauthenticated_senders"] == 1
        names = {x["name"]: x for x in s["senders"]}
        assert names["Google"]["verdict"] == "pass" and names["Google"]["ips"][0]["ptr"] == "mail-x.google.com"
        assert names["Unknown sender"]["verdict"] == "fail"
        assert len(s["by_day"]) == 30 and sum(d["passed"] for d in s["by_day"]) == 120

    def test_identify_caches(self, domain, monkeypatch):
        calls = []
        sources.identify(["209.85.1.1"], lookup=lambda ip: calls.append(ip) or "x.sendgrid.net")
        sources.identify(["209.85.1.1"], lookup=lambda ip: calls.append(ip) or "")
        assert calls == ["209.85.1.1"] and SourceIp.objects.get(ip="209.85.1.1").provider == "SendGrid"

    def test_provider_names(self):
        assert sources.provider_for("mail-sor-f41.google.com") == "Google"
        assert sources.provider_for("notgoogle.com") == ""
        assert sources.label("1.2.3.4", "", "", ["em.sendgrid.net"]) == "SendGrid"
        assert sources.label("1.2.3.4", "host.isp.net", "", []) == "isp.net"

    def _scan(self, domain, record):
        rua = [u.strip() for u in record.split("rua=")[1].split(";")[0].split(",")] if "rua=" in record else []
        scan = DnsScan.objects.create(
            domain=domain,
            status="completed",
            created_at=timezone.now(),
            results={"dmarc": {"record": record, "data": {"rua": rua, "policy": "reject"}}},
        )
        domain.latest_scan = scan
        domain.save()

    def test_suggested_record_and_status(self, domain, settings):
        settings.DMARC_RUA_ADDRESS = "dmarc@mspointit.com"
        self._scan(domain, "v=DMARC1; p=reject; rua=mailto:me@acme.com")
        assert suggested_record(domain) == "v=DMARC1; p=reject; rua=mailto:me@acme.com,mailto:dmarc@mspointit.com"
        assert reporting_status(domain, None) == "not_configured"
        self._scan(domain, "v=DMARC1; p=reject; rua=mailto:me@acme.com,mailto:dmarc@mspointit.com")
        assert suggested_record(domain).count("dmarc@mspointit.com") == 1
        assert reporting_status(domain, None) == "waiting"
        assert reporting_status(domain, timezone.now()) == "receiving"
        self._scan(domain, "")
        assert reporting_status(domain, None) == "no_dmarc"
        assert suggested_record(domain) == "v=DMARC1; p=none; rua=mailto:dmarc@mspointit.com"


# --- API -----------------------------------------------------------------------


@pytest.mark.django_db
class TestApi:
    def test_org_and_domain_views(self, domain, client_for, make_user):
        ingest_bytes(report_xml())
        owner = domain.organization.owner
        c = client_for(owner)
        r = c.get(f"/api/v1/organizations/{domain.organization_id}/dmarc/")
        assert r.status_code == 200 and r.data["totals"]["messages"] == 127
        assert r.data["domains"][0]["name"] == "acme.com" and r.data["rua_address"]
        r = c.get(f"/api/v1/domains/{domain.id}/dmarc/?days=7")
        assert r.status_code == 200 and r.data["reports"][0]["reporter"] == "google.com"
        assert c.get(f"/api/v1/domains/{domain.id}/dmarc/?days=5").status_code == 400
        outsider = client_for(make_user("x@other.com"))
        assert outsider.get(f"/api/v1/organizations/{domain.organization_id}/dmarc/").status_code == 404
        assert outsider.get(f"/api/v1/domains/{domain.id}/dmarc/").status_code == 404

    def test_upload(self, domain, client_for, make_user):
        owner = domain.organization.owner
        c = client_for(owner)
        url = f"/api/v1/domains/{domain.id}/dmarc/upload/"
        f = SimpleUploadedFile("r.xml.gz", gz(report_xml()), content_type="application/gzip")
        r = c.post(url, {"file": f}, format="multipart")
        assert r.status_code == 201 and r.data["stored"] == 1
        f = SimpleUploadedFile("r.xml", report_xml(domain="other.com"))
        r = c.post(url, {"file": f}, format="multipart")
        assert r.status_code == 400 and "not acme.com" in str(r.data)
        f = SimpleUploadedFile("r.txt", b"hello")
        assert c.post(url, {"file": f}, format="multipart").status_code == 400

        viewer = make_user("viewer@acme.com")
        Membership.objects.create(organization=domain.organization, user=viewer, role=Role.VIEWER)
        f = SimpleUploadedFile("r.xml", report_xml(report_id="v"))
        assert client_for(viewer).post(url, {"file": f}, format="multipart").status_code == 403

    def test_demo_workspace_has_sample_reports(self, make_user, client_for):
        user = make_user("demo@x.com")
        c = client_for(user)
        org_id = c.post("/api/v1/organizations/demo/").data["id"]
        r = c.get(f"/api/v1/organizations/{org_id}/dmarc/")
        assert r.status_code == 200 and r.data["totals"]["messages"] > 1000
        names = {s["name"] for s in r.data["senders"]}
        assert {"Google", "Microsoft 365", "Mailchimp"} <= names
        assert any(s["verdict"] == "fail" for s in r.data["senders"])
        statuses = {d["name"]: d["status"] for d in r.data["domains"]}
        assert statuses["harbour-dental.example"] == "receiving"
        assert statuses["brightpath-law.example"] == "no_dmarc"
