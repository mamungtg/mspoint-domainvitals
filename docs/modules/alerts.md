# Alerts and notifications

Code: `backend/apps/alerts/`. Tests: `backend/tests/test_alerts.py`.

## Alerts and notices

| Kind | Type | Raised by | Severity |
| --- | --- | --- | --- |
| `check` | Problem | A DNS scan where SPF, DKIM, DMARC, MX or DNS is `fail` or `warn` | critical (fail) / warning (warn) |
| `certificate` | Problem | A TLS check that is expired, expires within 7 days or fails (critical); expires within 30 days, warns or cannot connect (warning) | |
| `dns_change` | Notice | Record sets that changed between two scans (one notice per scan) | info |
| `dmarc_sender` | Notice | Mail failing SPF and DKIM from IPs that had not sent for the domain in the previous 90 days (one notice per domain per mailbox batch) | warning |

A **problem** is keyed per check or host (`check:<check>:<domain>`, `cert:<host>`) and has one open row at a time (unique constraint):

- **Opens** the first time it is seen, and notifies.
- **Escalates** from warning to critical, notifies and clears the acknowledgement.
- **Resolves** when a scan finds it fixed, and notifies.

Any other change (detail text, day count) updates the alert quietly, so a problem that stays broken is not re-sent every day. A check whose lookup failed (`error`) leaves the alert as it is.

Demo workspaces never raise alerts; they show a fixed sample, refreshed daily.

## Channels

Each workspace has channels. New workspaces start with **Owners and admins** (email, all events, warnings and above).

| Type | Target | Format |
| --- | --- | --- |
| Email | Owners/admins and/or up to 10 addresses | Branded HTML + text, one message per recipient |
| Slack | `https://hooks.slack.com/...` incoming webhook | Block Kit |
| Microsoft Teams | Teams Workflow webhook (`*.webhook.office.com`, `*.logic.azure.com`, Power Automate) | Adaptive Card 1.4 |
| Webhook | Any public `https` URL | JSON, signed |

Each channel picks event kinds and a minimum severity (applies to problems; notices of a chosen kind are always sent).

### Webhook payload

```json
{"event": "opened|escalated|resolved|notice|test", "sent_at": "...",
 "organization": {"id": "...", "name": "..."},
 "alert": {"id": "...", "kind": "check", "severity": "critical", "status": "open", "title": "...",
           "detail": "...", "domain": "example.com", "opened_at": "...", "resolved_at": null, "url": "...", "data": {}}}
```

Headers: `X-DomainVitals-Event` and `X-DomainVitals-Signature: sha256=<hex HMAC-SHA256 of the raw body with the channel's signing secret>`. Managers see the secret on the channel card.

### Delivery and safety

- Deliveries are queued after the database commit (`alerts.deliver`). A failed delivery is retried up to 3 times with backoff (1, 2 and 4 minutes). The result is kept in `Delivery`, and the last error is shown on the channel.
- Outbound HTTP is `https` only. The host must resolve to public addresses only (`is_public_ip`), redirects are not followed, and the timeout is 10 s.
- **Send test** delivers synchronously and reports the result.

## API

| Endpoint | Who |
| --- | --- |
| `GET organizations/{id}/alerts/?status=open\|resolved\|notice` | Any member (counts + up to 200 items) |
| `POST alerts/{id}/acknowledge/` | Owner, admin, member |
| `GET organizations/{id}/alert-channels/` | Any member (signing secret only for managers) |
| `POST organizations/{id}/alert-channels/`, `PATCH`/`DELETE alert-channels/{id}/`, `POST alert-channels/{id}/test/` | Owner, admin |
