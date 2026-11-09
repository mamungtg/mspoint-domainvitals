import pytest

from apps.dns_monitor.checks import run_checks, verify_ownership
from apps.dns_monitor.checks.dkim import check_dkim
from apps.dns_monitor.checks.dmarc import check_dmarc
from apps.dns_monitor.checks.mx import check_mx
from apps.dns_monitor.checks.spf import check_spf
from apps.dns_monitor.resolver import DnsLookupError, FakeResolver
from apps.domains.demo import KEY_1024, KEY_2048
from apps.domains.validation import InvalidDomain, normalize_domain

D = "example.com"


def codes(res):
    return {f.code for f in res.findings}


def spf(record_or_records, extra=None):
    recs = record_or_records if isinstance(record_or_records, list) else [record_or_records]
    zone = {D: {"TXT": recs}}
    zone.update(extra or {})
    return check_spf(D, FakeResolver(zone))


class TestSpf:
    def test_missing(self):
        r = check_spf(D, FakeResolver({D: {"TXT": ["google-site-verification=x"]}}))
        assert r.status == "fail" and "spf_missing" in codes(r)

    def test_valid_hard_fail(self):
        r = spf("v=spf1 ip4:192.0.2.1 -all")
        assert r.status == "pass" and r.data["lookups"] == 0

    def test_softfail_is_info_only(self):
        r = spf("v=spf1 ip4:192.0.2.1 ~all")
        assert r.status == "pass" and "spf_softfail" in codes(r)

    def test_multiple_records(self):
        assert "spf_multiple" in codes(spf(["v=spf1 -all", "v=spf1 ~all"]))

    def test_plus_all(self):
        r = spf("v=spf1 +all")
        assert r.status == "fail" and "spf_plus_all" in codes(r)

    def test_neutral_and_missing_all(self):
        assert "spf_neutral_all" in codes(spf("v=spf1 ip4:192.0.2.1 ?all"))
        assert "spf_no_all" in codes(spf("v=spf1 ip4:192.0.2.1"))

    def test_lookup_counting_through_includes(self):
        extra = {f"s{i}.example": {"TXT": [f"v=spf1 include:n{i}.example -all"]} for i in range(6)}
        extra.update({f"n{i}.example": {"TXT": ["v=spf1 ip4:192.0.2.0/24 -all"]} for i in range(6)})
        r = spf("v=spf1 " + " ".join(f"include:s{i}.example" for i in range(6)) + " -all", extra)
        assert r.data["lookups"] == 12 and "spf_too_many_lookups" in codes(r)

    def test_near_limit_warning(self):
        extra = {f"s{i}.example": {"TXT": ["v=spf1 -all"]} for i in range(9)}
        r = spf("v=spf1 " + " ".join(f"include:s{i}.example" for i in range(9)) + " -all", extra)
        assert r.status == "warn" and "spf_near_limit" in codes(r)

    def test_include_loop(self):
        extra = {
            "a.example": {"TXT": ["v=spf1 include:b.example -all"]},
            "b.example": {"TXT": ["v=spf1 include:a.example -all"]},
        }
        assert "spf_loop" in codes(spf("v=spf1 include:a.example -all", extra))

    def test_include_without_spf(self):
        r = spf("v=spf1 include:nothing.example -all")
        assert "spf_include_missing" in codes(r) and r.data["void_lookups"] == 1

    def test_unknown_mechanism(self):
        assert "spf_syntax" in codes(spf("v=spf1 ip5:1.2.3.4 -all"))

    def test_redirect_counts_and_satisfies_all(self):
        r = spf("v=spf1 redirect=_spf.example", {"_spf.example": {"TXT": ["v=spf1 ip4:192.0.2.0/24 -all"]}})
        assert r.status == "pass" and r.data["lookups"] == 1

    def test_timeout_is_error_not_failure(self):
        r = check_spf(D, FakeResolver({D: {"TXT": DnsLookupError}}))
        assert r.status == "error" and not r.findings


class TestDmarc:
    def zone(self, rec):
        return FakeResolver({f"_dmarc.{D}": {"TXT": [rec] if rec else []}})

    def test_missing(self):
        assert "dmarc_missing" in codes(check_dmarc(D, self.zone(None)))

    def test_reject_with_rua_passes(self):
        r = check_dmarc(D, self.zone("v=DMARC1; p=reject; rua=mailto:d@example.com"))
        assert r.status == "pass" and r.data["policy"] == "reject"

    def test_p_none_warns(self):
        r = check_dmarc(D, self.zone("v=DMARC1; p=none; rua=mailto:d@example.com"))
        assert r.status == "warn" and "dmarc_p_none" in codes(r)

    def test_invalid_policy(self):
        assert "dmarc_bad_policy" in codes(check_dmarc(D, self.zone("v=DMARC1; p=block")))

    def test_partial_pct_sp_none_and_no_rua(self):
        r = check_dmarc(D, self.zone("v=DMARC1; p=reject; sp=none; pct=25"))
        assert {"dmarc_partial_pct", "dmarc_sp_none", "dmarc_no_rua"} <= codes(r)

    def test_multiple(self):
        z = FakeResolver({f"_dmarc.{D}": {"TXT": ["v=DMARC1; p=none", "v=DMARC1; p=reject"]}})
        assert "dmarc_multiple" in codes(check_dmarc(D, z))


class TestDkim:
    def test_found_2048(self):
        r = check_dkim(D, FakeResolver({f"google._domainkey.{D}": {"TXT": [KEY_2048("a")]}}))
        assert r.status == "pass" and r.data["selectors"][0]["bits"] == 2048

    def test_1024_warns(self):
        r = check_dkim(D, FakeResolver({f"k1._domainkey.{D}": {"TXT": [KEY_1024("a")]}}))
        assert r.status == "warn" and "dkim_1024" in codes(r)

    def test_custom_selector_is_checked(self):
        r = check_dkim(D, FakeResolver({f"acme2025._domainkey.{D}": {"TXT": [KEY_2048("b")]}}), ["Acme2025"])
        assert r.status == "pass" and r.data["selectors"][0]["selector"] == "acme2025"

    def test_not_found(self):
        r = check_dkim(D, FakeResolver({}))
        assert r.status == "warn" and "dkim_not_found" in codes(r)

    def test_revoked_only(self):
        r = check_dkim(D, FakeResolver({f"s1._domainkey.{D}": {"TXT": ["v=DKIM1; p="]}}))
        assert "dkim_not_found" in codes(r)


class TestMx:
    def test_ok(self):
        r = check_mx(D, FakeResolver({D: {"MX": [(10, "mx.example.com")]}, "mx.example.com": {"A": ["192.0.2.1"]}}))
        assert r.status == "pass" and r.data["hosts"][0]["resolves"]

    def test_nxdomain(self):
        assert "domain_nxdomain" in codes(check_mx(D, FakeResolver({})))

    def test_null_mx(self):
        r = check_mx(D, FakeResolver({D: {"MX": [(0, ".")]}}))
        assert r.status == "pass" and r.data["null_mx"]

    def test_unresolvable_host(self):
        r = check_mx(D, FakeResolver({D: {"MX": [(10, "gone.example.com")]}}))
        assert r.status == "fail" and "mx_unresolvable" in codes(r)


def test_run_checks_scores_and_summarises():
    zone = {D: {"TXT": ["v=spf1 +all"], "MX": []}}
    out = run_checks(D, FakeResolver(zone))
    assert out["summary"] == {"spf": "fail", "dkim": "warn", "dmarc": "fail", "mx": "warn"}
    assert out["score"] == 100 - 25 * 2 - 10 * 2 and out["overall"] == "fail"


def test_verify_ownership():
    z = FakeResolver({f"_domainvitals.{D}": {"TXT": ["domainvitals-verify=abc", "other"]}})
    assert verify_ownership(D, "abc", z)
    assert not verify_ownership(D, "abcd", z)
    assert not verify_ownership("other.com", "abc", z)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Example.COM", "example.com"),
        ("https://www.Example.com/path?x=1", "www.example.com"),
        ("example.com.", "example.com"),
        ("user@example.com", "example.com"),
        ("bücher.de", "xn--bcher-kva.de"),
    ],
)
def test_normalize_domain_ok(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "localhost", "192.168.1.1", "*.example.com", "-bad.com", "a" * 64 + ".com", "ex ample.com"]
)
def test_normalize_domain_rejects(raw):
    with pytest.raises(InvalidDomain):
        normalize_domain(raw)
