"""Store parsed reports and read them from the reporting mailbox."""

from __future__ import annotations

import email
import email.policy
import imaplib
import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction

from apps.domains.models import Domain

from .models import DmarcRecord, DmarcReport
from .parser import MAX_INPUT, ParsedReport, ReportError, parse_file

log = logging.getLogger(__name__)

ATTACHMENT_TYPES = {
    "application/gzip",
    "application/x-gzip",
    "application/zip",
    "application/x-zip-compressed",
    "application/xml",
    "text/xml",
    "application/octet-stream",
}
MAX_MESSAGE = 15 * 1024 * 1024
MAX_PER_RUN = 200


@dataclass
class IngestResult:
    stored: int = 0
    duplicates: int = 0
    unknown_domain: int = 0
    invalid: int = 0
    reports: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def is_monitored(domain_name: str) -> bool:
    return Domain.objects.filter(name=domain_name, verified_at__isnull=False).exists()


def store_report(parsed: ParsedReport, source: str = DmarcReport.Source.MAIL) -> DmarcReport | None:
    """Save a report and its rows. Returns None if it was already stored."""
    mid = parsed.date_begin + (parsed.date_end - parsed.date_begin) / 2
    try:
        with transaction.atomic():
            report = DmarcReport.objects.create(
                domain_name=parsed.domain,
                reporter=parsed.reporter,
                reporter_email=parsed.reporter_email,
                report_id=parsed.report_id,
                date_begin=parsed.date_begin,
                date_end=parsed.date_end,
                policy=parsed.policy,
                message_count=min(parsed.message_count, 2**31 - 1),
                source=source,
            )
            DmarcRecord.objects.bulk_create(
                [
                    DmarcRecord(
                        report=report,
                        domain_name=parsed.domain,
                        day=mid.date(),
                        source_ip=r.source_ip,
                        count=r.count,
                        disposition=r.disposition,
                        dkim_aligned=r.dkim_aligned,
                        spf_aligned=r.spf_aligned,
                        header_from=r.header_from,
                        envelope_from=r.envelope_from,
                        dkim=r.dkim,
                        spf=r.spf,
                    )
                    for r in parsed.records
                ],
                batch_size=1000,
            )
    except IntegrityError:
        return None
    return report


def ingest_bytes(data: bytes, *, source=DmarcReport.Source.MAIL, only_domain: str | None = None) -> IngestResult:
    """Parse one file and store every report in it that belongs to a monitored
    domain. ``only_domain`` restricts an upload to the domain it was made for."""
    res = IngestResult()
    try:
        parsed = parse_file(data)
    except ReportError as e:
        res.invalid += 1
        res.errors.append(str(e))
        return res
    for p in parsed:
        if only_domain is not None and p.domain != only_domain:
            res.invalid += 1
            res.errors.append(f"This report is for {p.domain}, not {only_domain}.")
            continue
        if only_domain is None and not is_monitored(p.domain):
            res.unknown_domain += 1
            continue
        report = store_report(p, source)
        if report is None:
            res.duplicates += 1
        else:
            res.stored += 1
            res.reports.append(report)
    return res


def attachments(raw: bytes) -> list[bytes]:
    """Report files attached to (or forming the body of) a report email."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    out = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        name = (part.get_filename() or "").lower()
        if ctype not in ATTACHMENT_TYPES and not name.endswith((".xml", ".gz", ".zip")):
            continue
        payload = part.get_payload(decode=True)
        if payload and len(payload) <= MAX_INPUT:
            out.append(payload)
    return out


def ingest_message(raw: bytes) -> IngestResult:
    total = IngestResult()
    for data in attachments(raw):
        r = ingest_bytes(data)
        total.stored += r.stored
        total.duplicates += r.duplicates
        total.unknown_domain += r.unknown_domain
        total.invalid += r.invalid
        total.reports += r.reports
    return total


def mailbox_configured() -> bool:
    return bool(settings.DMARC_IMAP_HOST and settings.DMARC_IMAP_USER and settings.DMARC_IMAP_PASSWORD)


def poll_mailbox(connect=None) -> IngestResult:
    """Read unread messages from the reporting mailbox and mark them read.

    A cache lock stops two workers reading the mailbox at the same time.
    Messages that fail are still marked read so one bad email cannot block the
    queue; the error is logged.
    """
    total = IngestResult()
    if not mailbox_configured() and connect is None:
        return total
    if not cache.add("dmarc:poll-lock", 1, timeout=600):
        return total
    try:
        conn = (
            connect() if connect else imaplib.IMAP4_SSL(settings.DMARC_IMAP_HOST, settings.DMARC_IMAP_PORT, timeout=30)
        )
        try:
            if connect is None:
                conn.login(settings.DMARC_IMAP_USER, settings.DMARC_IMAP_PASSWORD)
            conn.select(settings.DMARC_IMAP_FOLDER)
            _, data = conn.search(None, "UNSEEN")
            ids = (data[0] or b"").split()[:MAX_PER_RUN]
            for num in ids:
                try:
                    _, size_data = conn.fetch(num, "(RFC822.SIZE)")
                    size = int(size_data[0].split(b"RFC822.SIZE ")[1].split(b")")[0])
                    if size > MAX_MESSAGE:
                        log.warning("dmarc: skipping message %s (%s bytes)", num, size)
                    else:
                        _, msg_data = conn.fetch(num, "(BODY.PEEK[])")
                        r = ingest_message(msg_data[0][1])
                        total.stored += r.stored
                        total.duplicates += r.duplicates
                        total.unknown_domain += r.unknown_domain
                        total.invalid += r.invalid
                        total.reports += r.reports
                except Exception:
                    log.exception("dmarc: failed to process message %s", num)
                    total.invalid += 1
                conn.store(num, "+FLAGS", "\\Seen")
        finally:
            try:
                conn.logout()
            except Exception:
                log.debug("dmarc: IMAP logout failed", exc_info=True)
    finally:
        cache.delete("dmarc:poll-lock")
    log.info(
        "dmarc: stored=%s duplicates=%s unknown=%s invalid=%s",
        total.stored,
        total.duplicates,
        total.unknown_domain,
        total.invalid,
    )
    return total
