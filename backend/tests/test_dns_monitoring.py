import pytest
from django.utils import timezone

from apps.dns_monitor.changes import diff_records
from apps.dns_monitor.checks import run_checks
from apps.dns_monitor.checks.infra import check_infra
from apps.dns_monitor.checks.spf import check_spf
from apps.dns_monitor.models import DnsChange, DnsScan
from apps.dns_monitor.propagation import check_propagation, find_zone
from apps.dns_monitor.resolver import DnsLookupError, FakeResolver
from apps.dns_monitor.services import execute_scan
from apps.domains.demo import ensure_demo_workspace
from apps.domains.models import Domain

D = "acme.com"


def zone(**over):
    z = {
        D: {
            "NS": ["ns1.dns.net", "ns2.dns.net"],
            "SOA": [f"ns1.dns.net. admin.{D}. 2026110901 7200 3600 1209600 3600"],
            "A": ["203.0.113.5"],
            "MX": [(10, "mx.mail.net")],
            "TXT": ["v=spf1 include:_spf.mail.net -all"],
            "TTL": {"NS": 86400, "MX": 3600, "A": 3600},
        },
        f"www.{D}": {"CNAME": [D], "A": ["203.0.113.5"]},
        "_spf.mail.net": {"TXT": ["v=spf1 ip4:198.51.100.0/24 -all"]},
        "mx.mail.net": {"A": ["198.51.100.25"]},
        "ns1.dns.net": {"A": ["192.0.2.1"]},
        "ns2.dns.net": {"A": ["192.0.2.2"]},
    }
    for k, v in over.items():
        z.setdefault(k.replace("__", "."), {}).update(v)
    return z


def codes(r):
    return {f.code for f in r.findings}


def infra(z, hosts=None):
    return check_infra(D, FakeResolver(z), hosts=hosts or [f"www.{D}"], dkim_selectors=[])


# ---------- infrastructure ----------------------------------------------------------


def test_healthy_zone_has_full_inventory():
    r = infra(zone())
    assert r.status == "pass" and not r.findings
    inv = r.data["records"]
    assert {f"{D} NS", f"{D} SOA", f"{D} A", f"{D} MX", f"{D} TXT", f"www.{D} CNAME"} <= set(inv)
    assert inv[f"{D} NS"]["ttl"] == 86400 and inv[f"{D} NS"]["values"] == ["ns1.dns.net.", "ns2.dns.net."]
    assert r.data["soa"]["serial"] == 2026110901


def test_single_ns_missing_ns_and_soa():
    assert "dns_ns_single" in codes(infra(zone(**{D: {"NS": ["ns1.dns.net"]}})))
    r = infra(zone(**{D: {"NS": [], "SOA": []}}))
    assert "dns_ns_missing" in codes(r) and r.status == "fail"


def test_serial_mismatch_and_lame_server():
    z = zone()
    z[D]["AUTH"] = [
        {"ns": "ns1.dns.net", "ip": "192.0.2.1", "authoritative": True, "serial": 5, "error": ""},
        {"ns": "ns2.dns.net", "ip": "192.0.2.2", "authoritative": True, "serial": 4, "error": ""},
        {
            "ns": "ns3.old.net",
            "ip": "192.0.2.3",
            "authoritative": False,
            "serial": None,
            "error": "Answered REFUSED without authority",
        },
    ]
    c = codes(infra(z))
    assert {"dns_soa_serial_mismatch", "dns_ns_lame"} <= c


def test_dangling_cname_is_critical():
    r = infra(zone(**{f"www__{D}": {"CNAME": ["gone.oldhost.net"], "A": []}}))
    assert "dns_dangling_cname" in codes(r) and r.status == "fail"


def test_cname_at_apex_and_no_address():
    assert "dns_cname_apex" in codes(infra(zone(**{D: {"CNAME": ["lb.host.net"]}})))
    assert "dns_apex_no_address" in codes(infra(zone(**{D: {"A": []}})))


def test_ttl_and_soa_advice():
    z = zone(**{D: {"TTL": {"NS": 60, "MX": 60, "A": 172800}, "SOA": [f"ns1.dns.net. admin.{D}. 1 60 30 3600 10"]}})
    c = codes(infra(z))
    assert {"dns_ttl_low", "dns_ttl_high", "dns_soa_values"} <= c


def test_lookup_timeout_marks_check_as_error():
    z = zone(**{D: {"NS": DnsLookupError}})
    assert infra(z).status == "error"


# ---------- SPF syntax ----------------------------------------------------------------


def test_spf_cidr_and_duplicates():
    z = zone(**{D: {"TXT": ["v=spf1 ip4:300.1.1.1 ip6:2001:db8::/129 ip4:192.0.2.0/24 ip4:192.0.2.0/24 -all"]}})
    r = check_spf(D, FakeResolver(z))
    msgs = " ".join(f.detail for f in r.findings)
    assert "spf_syntax" in codes(r) and "300.1.1.1" in msgs and "2001:db8::/129" in msgs
    assert "spf_duplicate" in codes(r)


# ---------- change detection ------------------------------------------------------------


def test_diff_detects_every_kind():
    old = {
        "a.com A": {"ttl": 300, "values": ["1.1.1.1"]},
        "a.com MX": {"ttl": 300, "values": ["10 mx."]},
        "a.com TXT": {"ttl": 300, "values": ['"x"']},
    }
    new = {
        "a.com A": {"ttl": 300, "values": ["2.2.2.2"]},
        "a.com MX": {"ttl": 600, "values": ["10 mx."]},
        "a.com NS": {"ttl": 300, "values": ["ns."]},
    }
    kinds = {(c["rtype"], c["kind"]) for c in diff_records(old, new)}
    assert kinds == {("A", "changed"), ("MX", "ttl"), ("TXT", "removed"), ("NS", "added")}


@pytest.mark.django_db
def test_scans_record_changes_but_not_on_baseline_or_errors(make_user, make_org):
    owner = make_user()
    d = Domain.objects.create(organization=make_org(owner), name=D, verified_at=timezone.now())

    def scan(z):
        s = DnsScan.objects.create(domain=d, created_at=timezone.now())
        return execute_scan(s, FakeResolver(z))

    first = scan(zone())
    assert first.records and DnsChange.objects.count() == 0  # baseline
    scan(zone(**{D: {"A": ["203.0.113.9"]}}))
    ch = DnsChange.objects.get()
    assert (ch.name, ch.rtype, ch.kind, ch.old_values, ch.new_values) == (
        D,
        "A",
        "changed",
        ["203.0.113.5"],
        ["203.0.113.9"],
    )
    scan(zone(**{D: {"NS": DnsLookupError}}))  # failed lookup must not look like deleted records
    assert DnsChange.objects.count() == 1


# ---------- propagation ------------------------------------------------------------------


def test_propagation_consensus_offline():
    r = check_propagation(f"www.{D}", "A", resolver=FakeResolver(zone()), live=False)
    assert r["zone"] == D and r["propagated"] and r["matched"] == r["total"] == 2 + 4
    assert find_zone(f"deep.www.{D}", FakeResolver(zone())) == D


# ---------- API ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_records_changes_api_and_isolation(make_user, client_for):
    u = make_user()
    org = ensure_demo_workspace(u)
    dom = Domain.objects.get(organization=org, name="harbour-dental.example")
    c = client_for(u)
    rec = c.get(f"/api/v1/domains/{dom.id}/records/").data
    types = {(r["name"], r["type"]) for r in rec["records"]}
    assert ("harbour-dental.example", "NS") in types and ("www.harbour-dental.example", "CNAME") in types
    assert len(rec["name_servers"]) == 2
    changes = c.get(f"/api/v1/domains/{dom.id}/changes/").data
    assert any(ch["rtype"] == "A" and ch["kind"] == "changed" for ch in changes)  # hosting move in the sample
    prop = c.get(f"/api/v1/domains/{dom.id}/propagation/", {"name": "www.harbour-dental.example", "type": "A"}).data
    assert prop["propagated"]
    assert c.get(f"/api/v1/domains/{dom.id}/propagation/", {"name": "evil.net", "type": "A"}).status_code == 400
    ov = c.get(f"/api/v1/organizations/{org.id}/overview/").data
    assert ov["recent_changes"] and "dns" in ov["checks"]
    outsider = client_for(make_user("x@example.com"))
    for path in ("records", "changes"):
        assert outsider.get(f"/api/v1/domains/{dom.id}/{path}/").status_code == 404


@pytest.mark.django_db
def test_watch_names_validation(make_user, make_org, client_for):
    owner = make_user()
    d = Domain.objects.create(organization=make_org(owner), name=D)
    c = client_for(owner)
    r = c.patch(f"/api/v1/domains/{d.id}/", {"dns_watch_names": ["Mail.ACME.com", "mail.acme.com"]}, format="json")
    assert r.status_code == 200 and r.data["dns_watch_names"] == ["mail.acme.com"]
    assert c.patch(f"/api/v1/domains/{d.id}/", {"dns_watch_names": ["evil.net"]}, format="json").status_code == 400


def test_run_checks_includes_dns_category():
    out = run_checks(D, FakeResolver(zone()), [], hosts=[f"www.{D}"])
    assert "dns" in out["summary"] and out["results"]["dns"]["data"]["records"]


def test_soa_serial_bump_alone_is_not_a_change():
    from apps.dns_monitor.changes import diff_records

    soa = "ns1.x. host.x. {} 7200 3600 1209600 3600"
    old = {"x SOA": {"ttl": 3600, "values": [soa.format(1)]}}
    assert diff_records(old, {"x SOA": {"ttl": 3600, "values": [soa.format(2)]}}) == []
    changed = {"x SOA": {"ttl": 3600, "values": ["ns1.x. host.x. 2 7200 3600 1209600 300"]}}
    assert [c["kind"] for c in diff_records(old, changed)] == ["changed"]
