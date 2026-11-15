"""Parse DMARC aggregate (RUA) reports.

Receivers send XML (RFC 7489 appendix C, and the newer dmarc-2.0 namespace),
usually gzip- or zip-compressed. Everything here treats the input as hostile:
XML is parsed with defusedxml (no entities, no external references), archives
are size-capped while decompressing so a small file cannot expand into a huge
one, and every field is length- and range-checked.
"""

from __future__ import annotations

import gzip
import io
import ipaddress
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_INPUT = 10 * 1024 * 1024  # compressed upload or attachment
MAX_XML = 25 * 1024 * 1024  # one decompressed report
MAX_ZIP_MEMBERS = 10
MAX_RECORDS = 10_000
MAX_COUNT = 10_000_000
MAX_PERIOD_DAYS = 31


class ReportError(ValueError):
    """The file is not a usable DMARC aggregate report."""


@dataclass
class ParsedRecord:
    source_ip: str
    count: int
    disposition: str
    dkim_aligned: bool
    spf_aligned: bool
    header_from: str
    envelope_from: str
    dkim: list[dict] = field(default_factory=list)
    spf: list[dict] = field(default_factory=list)


@dataclass
class ParsedReport:
    reporter: str
    reporter_email: str
    report_id: str
    date_begin: datetime
    date_end: datetime
    domain: str
    policy: dict
    records: list[ParsedRecord]

    @property
    def message_count(self) -> int:
        return sum(r.count for r in self.records)


def _read_capped(stream, limit: int) -> bytes:
    out = stream.read(limit + 1)
    if len(out) > limit:
        raise ReportError("The report is larger than 25 MB once decompressed.")
    return out


def extract_documents(data: bytes) -> list[bytes]:
    """Return the XML documents inside raw XML, gzip or zip data."""
    if len(data) > MAX_INPUT:
        raise ReportError("The file is larger than 10 MB.")
    if data[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as g:
                return [_read_capped(g, MAX_XML)]
        except (OSError, EOFError) as e:
            raise ReportError("The gzip file is damaged.") from e
    if data[:4] == b"PK\x03\x04":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise ReportError("The zip file is damaged.") from e
        members = [m for m in zf.infolist() if not m.is_dir()]
        if not members or len(members) > MAX_ZIP_MEMBERS:
            raise ReportError("The zip file should contain one report.")
        docs = []
        for m in members:
            if m.file_size > MAX_XML:
                raise ReportError("The report is larger than 25 MB once decompressed.")
            with zf.open(m) as f:
                docs.append(_read_capped(f, MAX_XML))
        return docs
    stripped = data.lstrip()
    if stripped.startswith(b"<"):
        return [data]
    raise ReportError("This is not an XML, gzip or zip file.")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el, name):
    if el is None:
        return None
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el, name):
    return [c for c in el if _local(c.tag) == name] if el is not None else []


def _text(el, name, limit=255) -> str:
    c = _child(el, name)
    return ((c.text or "").strip()[:limit]) if c is not None else ""


def _int(value: str, what: str, lo: int = 0, hi: int = 2**62) -> int:
    try:
        n = int(value.strip())
    except (AttributeError, ValueError) as e:
        raise ReportError(f"The report has an invalid {what}.") from e
    if not lo <= n <= hi:
        raise ReportError(f"The report has an out-of-range {what}.")
    return n


def _domain(value: str) -> str:
    return value.strip().rstrip(".").lower()[:253]


def parse_report(xml: bytes) -> ParsedReport:
    try:
        root = SafeET.fromstring(xml, forbid_dtd=True)
    except DefusedXmlException as e:
        raise ReportError("The XML uses features that are not allowed in reports.") from e
    except SafeET.ParseError as e:
        raise ReportError("The file is not valid XML.") from e
    if _local(root.tag) != "feedback":
        raise ReportError("This XML is not a DMARC aggregate report.")

    meta = _child(root, "report_metadata")
    if meta is None:
        raise ReportError("The report has no metadata.")
    reporter = _text(meta, "org_name") or _text(meta, "email")
    report_id = _text(meta, "report_id")
    if not reporter or not report_id:
        raise ReportError("The report has no sender or report ID.")
    rng = _child(meta, "date_range")
    begin = _int(_text(rng, "begin"), "start date", 0, 4102444800)
    end = _int(_text(rng, "end"), "end date", 0, 4102444800)
    if end < begin or end - begin > MAX_PERIOD_DAYS * 86400:
        raise ReportError("The report period is not valid.")

    pp = _child(root, "policy_published")
    domain = _domain(_text(pp, "domain"))
    if not domain:
        raise ReportError("The report does not say which domain it covers.")
    policy = {k: _text(pp, k, 20).lower() for k in ("p", "sp", "pct", "adkim", "aspf", "np", "fo")}
    policy = {k: v for k, v in policy.items() if v}

    rows = _children(root, "record")
    if len(rows) > MAX_RECORDS:
        raise ReportError("The report has too many records.")
    records = []
    for rec in rows:
        row = _child(rec, "row")
        ip = _text(row, "source_ip", 64)
        try:
            ip = str(ipaddress.ip_address(ip))
        except ValueError as e:
            raise ReportError("The report has a record with an invalid IP address.") from e
        count = _int(_text(row, "count"), "message count", 0, MAX_COUNT)
        ev = _child(row, "policy_evaluated")
        ids = _child(rec, "identifiers")
        auth = _child(rec, "auth_results")
        dkim = [
            {
                "domain": _domain(_text(d, "domain")),
                "selector": _text(d, "selector", 63),
                "result": _text(d, "result", 20).lower(),
            }
            for d in _children(auth, "dkim")[:10]
        ]
        spf = [
            {"domain": _domain(_text(s, "domain")), "result": _text(s, "result", 20).lower()}
            for s in _children(auth, "spf")[:5]
        ]
        records.append(
            ParsedRecord(
                source_ip=ip,
                count=count,
                disposition=_text(ev, "disposition", 20).lower(),
                dkim_aligned=_text(ev, "dkim", 20).lower() == "pass",
                spf_aligned=_text(ev, "spf", 20).lower() == "pass",
                header_from=_domain(_text(ids, "header_from")),
                envelope_from=_domain(_text(ids, "envelope_from")),
                dkim=dkim,
                spf=spf,
            )
        )
    return ParsedReport(
        reporter=reporter,
        reporter_email=_text(meta, "email"),
        report_id=report_id,
        date_begin=datetime.fromtimestamp(begin, UTC),
        date_end=datetime.fromtimestamp(end, UTC),
        domain=domain,
        policy=policy,
        records=records,
    )


def parse_file(data: bytes) -> list[ParsedReport]:
    return [parse_report(doc) for doc in extract_documents(data)]
