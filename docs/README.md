# DomainVitals developer documentation

DomainVitals by MSPoint monitors the health of the domains a business sends email from and serves websites on: SPF, DKIM, DMARC, MX, DNS infrastructure, record changes and SSL/TLS certificates.

| Document | What it covers |
| --- | --- |
| [architecture.md](architecture.md) | Services, data model, request flow, security model |
| [modules/dns-monitoring.md](modules/dns-monitoring.md) | DNS checks, record inventory, change detection, propagation |
| [modules/dmarc-reports.md](modules/dmarc-reports.md) | Report ingestion, parsing limits, sender identification |
| [modules/ssl-monitoring.md](modules/ssl-monitoring.md) | Certificate scanning and evaluation |
| [modules/alerts.md](modules/alerts.md) | Alert lifecycle, channels, webhook signing |
| [modules/billing.md](modules/billing.md) | Plans, limits, Stripe Checkout, portal and webhooks |
| [modules/public-tools.md](modules/public-tools.md) | Free no-login tools, rate limits, SEO prerendering |
| [api.md](api.md) | REST endpoints (full schema at `/api/v1/docs/`) |
| [operations.md](operations.md) | Deploying, rolling back, everyday server tasks |
| [roadmap.md](roadmap.md) | Plans, pricing and what is built next |

## Working rules

- Every module ships with tests, and `pytest`, `ruff check`, `ruff format --check`, `makemigrations --check` and `npm run build` must all pass before a commit. CI enforces the same.
- No module is started until the previous one has been verified in the browser in light mode, dark mode and at 390 px width with no horizontal scroll.
- Network-facing code never contacts private or reserved IP addresses (SSRF guard in `apps/ssl_monitor/scanner.py::is_public_ip`).
- The demo workspace runs the real check engine against a fixed fake zone, so what customers see in the demo is exactly what the product does.
