# Architecture

## Services

| Service | Image | Role |
| --- | --- | --- |
| `web` | `domainvitals-web` | Nginx: serves the React build and proxies `/api/` to the backend. TLS with a Cloudflare Origin certificate, bound to 127.0.0.1 only. |
| `cloudflared` | `cloudflare/cloudflared` | Cloudflare Tunnel. The only way in from the internet (the server sits behind NAT). |
| `backend` | `domainvitals-backend` | Django 5.2 + DRF under Gunicorn. |
| `worker` | same | Celery worker: DNS scans, TLS scans, email. |
| `beat` | same | Celery beat: schedules recurring jobs. |
| `db` | `postgres:16` | Primary data store, sessions included. |
| `redis` | `redis:7.4` | Celery broker, cache, throttle counters. |

## Backend apps

| App | Responsibility |
| --- | --- |
| `accounts` | Users, email verification, password reset, session login with CSRF. |
| `organizations` | Workspaces, roles (owner, admin, member, viewer), invitations. Every query is scoped to the caller's memberships; outsiders get 404. |
| `domains` | Domains, ownership verification by TXT record, overview dashboard, public checker, demo workspace. |
| `dns_monitor` | Check engine (SPF, DKIM, DMARC, MX, DNS), resolvers, scans, record inventory, change history, propagation. |
| `ssl_monitor` | Monitored hosts, TLS handshakes, certificate evaluation, expiry reports. |

## Scheduled jobs

| Job | Every | What it does |
| --- | --- | --- |
| `dns_monitor.schedule_due_scans` | 15 min | Queues a scan for each monitored, verified domain whose last scan is about a day old. |
| `dns_monitor.recheck_verifications` | 6 h | Confirms the verification TXT is still published; monitoring stops after three days without it. |
| `ssl_monitor.schedule_due_tls_scans` | 30 min | Queues TLS scans that are due. |

## Scoring

Each check returns `pass`, `warn`, `fail` or `error` plus findings with a severity. The domain score starts at 100; each critical finding costs 25 and each warning 10 (floor 0). Info findings are advice only. A check that could not run (`error`) does not lower the score.

## Security model

- Session cookies (`HttpOnly`, `Secure`, `SameSite=Lax`) with CSRF required on every unsafe request, including anonymous ones.
- Rate limits per scope (login, register, password reset, tools, domain writes) stored in Redis.
- Tenant isolation: objects are fetched through the caller's memberships, and a missing membership returns 404 rather than 403 so IDs can't be probed.
- Viewers and the demo workspace are read-only.
- Outbound probes (TLS handshakes, authoritative DNS queries) go only to public IP addresses.
- Django admin is off in production unless `ENABLE_ADMIN` is set, and lives at a non-default path.
