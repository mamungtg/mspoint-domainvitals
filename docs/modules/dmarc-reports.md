# DMARC reports

Code: `backend/apps/dmarc/`. Tests: `backend/tests/test_dmarc.py`.

## How reports arrive

1. The customer adds the DomainVitals reporting address (`DMARC_RUA_ADDRESS`, default `dmarc@mspointit.com`) to the `rua=` tag of their DMARC record. The setup panel builds the exact record, keeping any address they already use.
2. Because that address is on a different domain, `mspointit.com` publishes `*._report._dmarc.mspointit.com TXT "v=DMARC1"` (RFC 7489 §7.1 external destination verification). Without it, receivers drop the reports.
3. Google, Microsoft, Yahoo and other receivers send one report per day per domain.
4. `dmarc.poll_dmarc_mailbox` (every 10 minutes) reads unread messages over IMAPS, extracts `.xml`, `.gz` and `.zip` attachments, parses them, and marks each message read. A cache lock keeps two workers from reading at once; a failing message is logged and still marked read so it cannot block the queue.
5. Reports are stored only for domains that are verified in at least one workspace; reports for anything else are dropped. Duplicates (same domain, reporter and report ID) are ignored.
6. `dmarc.identify_sources` resolves the reverse DNS of new sending IPs and maps them to a service (Google, Microsoft 365, SendGrid, Mailchimp, …). Results are cached for 30 days in `SourceIp`.

Customers can also import a report file by hand on **Domain → DMARC reports** (10 MB limit, must match the domain).

## Safety limits (`parser.py`)

| Limit | Value |
| --- | --- |
| Compressed file | 10 MB |
| One decompressed report | 25 MB, enforced while decompressing |
| Files inside a zip | 10 |
| Records per report | 10,000 |
| Report period | 31 days |

XML is parsed with defusedxml with DTDs forbidden, so entity expansion and external entities are rejected. IPs, dates and counts are validated.

## Data model

- `DmarcReport`: one report (domain name, reporter, report ID, period, published policy). Keyed by domain *name* so an agency and its client who both verify a domain both see its reports.
- `DmarcRecord`: one row per sending IP with message count, disposition, DKIM/SPF alignment, identifiers and raw auth results; `day` is the middle of the report period.
- `SourceIp`: reverse DNS name and service per IP.

Reports older than `DMARC_RETENTION_DAYS` (400) are deleted daily.

## What the dashboard shows

- Totals: messages, DMARC pass rate (aligned SPF **or** aligned DKIM), failures, quarantined and rejected.
- Daily pass/fail volume for 7, 30 or 90 days.
- Sending services grouped by name, with SPF/DKIM alignment and the IPs behind each. Verdict: **Authenticated** (≥ 95 % pass), **Not authenticated** (0 % pass and not a recognised service; usually spoofing), otherwise **Partly failing**, with advice on what to fix.
- Per domain reporting status: receiving (report in the last 4 days), waiting (record points at us, nothing yet), not set up, or no DMARC record.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DMARC_RUA_ADDRESS` | `dmarc@mspointit.com` | Address shown to customers |
| `DMARC_IMAP_HOST` / `PORT` | – / 993 | Mailbox server (IMAPS). Empty disables polling. |
| `DMARC_IMAP_USER` / `PASSWORD` | – | Mailbox login (use an app-specific password) |
| `DMARC_IMAP_FOLDER` | `INBOX` | Folder to read |
| `DMARC_RETENTION_DAYS` | 400 | How long reports are kept |
