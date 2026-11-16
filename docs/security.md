# Security

## Review, November 2026

| Area | Finding | Action |
| --- | --- | --- |
| Dependencies | Known vulnerabilities in Pillow (72), cryptography (14), DRF (5), dnspython (2), certifi (2) and react-router (3 high) | Upgraded to fixed releases: Pillow 13.0.0, cryptography 50.0.2, DRF 3.18.2, dnspython 2.9.2, certifi 2026.10.18, react-router-dom 6.30.6. `pip-audit` now reports nothing. |
| Dependencies | 2 moderate react-router advisories, fixed only in v7 | Not exploitable here: no server-side rendering, and the only redirect from user input (`?next=`) goes through `safeNext`. `safeNext` now also rejects backslashes, control characters and anything resolving to another origin. Tracked for the v7 upgrade. |
| Dependencies | No automatic checks | CI job **Dependency vulnerabilities** runs `pip-audit` and `npm audit --audit-level=high` on every PR and weekly. |
| Accounts | Sign-up said "An account with this email already exists", revealing who has an account | Same response for every address. An existing user gets a "you already have an account" mail; an unconfirmed one gets a new confirmation link. |
| Accounts | Password guessing was limited only per IP | Per-account lock: 10 failed attempts within 15 minutes locks sign-in for 15 minutes from any IP. A successful sign-in or password reset clears the count. |
| Rate limits | Behind the Cloudflare Tunnel every visitor had the same IP, so limits were shared by everyone | Fixed earlier (see `public-tools.md`): nginx trusts the tunnel for `CF-Connecting-IP`, `NUM_PROXIES = 1`. |
| Browser | No Content-Security-Policy; no HSTS on the HTML pages | nginx sends a strict CSP (same-origin scripts, fonts, images and connections; no framing; no plugins), HSTS for 1 year, COOP and a tighter Permissions-Policy. 11 pages tested with no CSP violations. |
| API | The OpenAPI schema and Swagger UI were public, mapping every endpoint | Staff only (`API_DOCS_PUBLIC=true` re-opens it for a public API). |
| API | Schema generation crashed on the logo endpoint | Fixed. A test now generates the schema. |
| Tenant isolation | Each module had its own tests, but nothing covered every route | `tests/test_tenant_isolation.py` walks the URL configuration and calls every route that takes an object ID (36 routes × 5 methods) as an owner of another workspace; each must answer 401, 403, 404 or 405. A new route with an unknown ID type fails the test until it is covered. |

## Controls in place

- **Authentication:**
  - Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax`, 7-day lifetime.
  - CSRF on every unsafe request, including anonymous ones.
  - Sign-in requires a confirmed email address.
  - Django password validators.
  - Rate limits per IP and per account.
- **Authorisation:** every object is fetched through the caller's membership; outsiders get 404. Roles: owner, admin, member, viewer. Billing is owner-only.
- **Untrusted input:**
  - DMARC XML: defusedxml, DTDs forbidden, size caps while decompressing.
  - Logos: Pillow verifies and re-encodes them.
  - Domain names are normalised and validated.
  - Paragraph text in PDFs is escaped.
- **Outbound requests:** TLS scans, authoritative DNS probes and webhooks go only to public IP addresses. Webhooks are `https` only, with no redirects, and are HMAC-signed.
- **Payments:** card data goes to Stripe Checkout and the Portal and never reaches DomainVitals. Webhooks are signature-verified and processed once.
- **Secrets:** kept only in the server `.env` and GitHub environment secrets. The Django admin is off in production.
- **Transport:** Cloudflare Tunnel (no open inbound ports), Origin certificate between Cloudflare and nginx, HSTS.

## Reporting a vulnerability

Email security@mspointit.com. We reply within 3 working days.
