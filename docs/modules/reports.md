# PDF and white-label reports

Code: `backend/apps/reports/` (`data.py` collects, `pdf.py` renders with ReportLab, `branding.py`, `tasks.py`),
`frontend/src/pages/ClientReports.tsx`. Tests: `backend/tests/test_reports.py`.

## Contents

1. **Cover:** the workspace name (or the domain, for a single-domain report), the period, who prepared it, and totals:
   - domains and average score
   - domains needing attention
   - certificates expiring within 30 days
   - open alerts
2. **All domains:** a table with each domain's score and its SPF, DKIM, DMARC, MX and DNS status. It is left out of single-domain reports.
3. **One page per domain:**
   - score and check statuses
   - score trend over the period (last scan of each day)
   - "What to fix": critical problems first, with the fix
   - certificates
   - DMARC summary (messages, pass rate, top 5 sending services)
   - DNS changes in the period
   - open alerts

Periods: 30 or 90 days. Up to 100 domains per report.

## Branding

- **Who gets white-label:** workspaces on Agency, MSP, Enterprise or the trial (`branding.white_label_allowed`).
- **What they can set:** company name, brand colour (`#RRGGBB`), footer text and a logo.
- **Everyone else:** reports carry DomainVitals branding.
- **Logos:** PNG or JPEG up to 1 MB.
  - Pillow verifies the file, refuses decompression bombs and re-encodes it as a PNG of at most 600×200 px, which drops metadata and any trailing data.
  - The logo is stored in the database (`ReportBranding.logo`).

The built-in PDF fonts cover Latin-1. Common Unicode punctuation is mapped to ASCII, and other characters (for example Bangla script) are replaced. Supporting more scripts would mean embedding a TTF font.

## Monthly mail

`ReportSchedule` holds the settings: on or off, and up to 10 recipients. Beat runs `reports.send_monthly_reports` every 6 hours. Once per calendar month, from the 1st, it mails each recipient the 30-day report for all verified domains as a PDF attachment, then records `last_sent_on`.

## API

| Endpoint | Who |
| --- | --- |
| `GET organizations/{id}/reports/pdf/?domain=&days=30\|90` | Any member (rate limit `reports`, 30/hour) |
| `GET/PATCH organizations/{id}/reports/branding/` | Read: member · Change: owner/admin |
| `GET/POST/DELETE organizations/{id}/reports/branding/logo/` | Read: member · Change: owner/admin |
| `GET/PUT organizations/{id}/reports/schedule/` | Read: member · Change: owner/admin |
