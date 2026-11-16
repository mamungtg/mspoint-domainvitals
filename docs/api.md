# API

Base path `/api/v1/`. Interactive schema: `/api/v1/docs/` (OpenAPI at `/api/v1/schema/`). All endpoints use session authentication; unsafe methods need the `X-CSRFToken` header from `GET auth/csrf/`.

| Area | Endpoints |
| --- | --- |
| Auth | `auth/csrf/`, `auth/register/`, `auth/login/`, `auth/logout/`, `auth/me/`, `auth/verify-email/`, `auth/verify-email/resend/`, `auth/password-reset/`, `auth/password-reset/confirm/`, `auth/password/change/` |
| Workspaces | `organizations/`, `organizations/{id}/`, `organizations/{id}/members/`, `organizations/{id}/invitations/`, `invitations/{id}/`, `invitations/accept/`, `memberships/{id}/`, `organizations/demo/` |
| Domains | `organizations/{id}/domains/` (GET, POST), `domains/{id}/` (GET, PATCH, DELETE), `domains/{id}/verify/`, `domains/{id}/scan/`, `domains/{id}/scans/`, `scans/{id}/`, `organizations/{id}/overview/` |
| DNS | `domains/{id}/records/`, `domains/{id}/changes/?name=&type=`, `domains/{id}/propagation/?name=&type=` |
| SSL/TLS | `organizations/{id}/certificates/`, `domains/{id}/tls-hosts/` (GET, POST), `tls-hosts/{id}/` (DELETE), `tls-hosts/{id}/scan/`, `tls-hosts/{id}/scans/` |
| DMARC | `organizations/{id}/dmarc/?days=` (7, 30 or 90), `domains/{id}/dmarc/?days=`, `domains/{id}/dmarc/upload/` (POST multipart `file`) |
| Alerts | `organizations/{id}/alerts/?status=`, `alerts/{id}/acknowledge/`, `organizations/{id}/alert-channels/`, `alert-channels/{id}/`, `alert-channels/{id}/test/` |
| Billing | `organizations/{id}/billing/`, `organizations/{id}/billing/checkout/` (owner), `organizations/{id}/billing/portal/` (owner), `billing/stripe/webhook/` (Stripe only, signed) |
| Reports | `organizations/{id}/reports/pdf/?domain=&days=`, `organizations/{id}/reports/branding/`, `organizations/{id}/reports/branding/logo/`, `organizations/{id}/reports/schedule/` |
| Public tools (no login; anonymous: CSRF + per-IP limits) | `tools/ssl/` (POST `{hostname, port}`), `tools/check/` (POST `{domain, check, selector}`; `check` is `all`, `spf`, `dkim`, `dmarc`, `mx` or `dns`), `tools/propagation/` (POST `{name, type}`) |

`PATCH domains/{id}/` accepts `monitoring_enabled`, `dkim_selectors` and `dns_watch_names`.

Rate limits (per user or IP, configurable by environment variable): login 10/min, register 5/hour, password reset 5/hour, email verification 20/hour, invitations 30/hour, tools 30/hour, domain writes 60/hour.
