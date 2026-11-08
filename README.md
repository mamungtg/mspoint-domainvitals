# MSPoint DomainVitals

Email authentication (SPF, DKIM, DMARC), DNS and SSL/TLS monitoring SaaS for agencies and MSPs.

| Part | Stack |
|---|---|
| Backend | Django 5.2 + DRF, PostgreSQL 16, Celery + Redis |
| Frontend | React 18 + TypeScript + Vite + Tailwind |
| Edge | Nginx (Cloudflare Origin Certificate, behind Cloudflare) |
| Delivery | GitHub Actions → GHCR images → self-hosted runner on the server |

## Repository layout

```
backend/            Django project (config/, apps/, common/, tests/)
frontend/           React SPA
infrastructure/     nginx/ config, scripts/deploy.sh
docker-compose.yml        local dev dependencies (Postgres, Redis)
docker-compose.prod.yml   production stack (copied to /opt/domainvitals)
.github/workflows/  ci.yml (tests) and deploy.yml (build + deploy)
```

## Local development

```bash
docker compose up -d                       # Postgres + Redis on localhost
cp .env.example .env                       # then set:
#   DJANGO_SECRET_KEY=dev-anything
#   DATABASE_URL=postgres://domainvitals:domainvitals@localhost:5432/domainvitals
#   REDIS_URL=redis://localhost:6379/0
cd backend && pip install -r requirements/dev.txt
python manage.py migrate && python manage.py runserver      # API on :8000
celery -A config worker -l info                            # optional, for emails
cd ../frontend && npm ci && npm run dev                    # SPA on :5173, /api proxied
```

Tests and lint: `cd backend && pytest && ruff check . && ruff format --check .`

## Delivery pipeline

1. Pull request or non-`main` push → **CI**: ruff, missing-migration check, pytest on Postgres, frontend build.
2. Push to `main` → **Deploy**: CI again → build `domainvitals-backend` and `domainvitals-web` images tagged with the commit SHA → push to GHCR → job on the self-hosted runner (label `domainvitals`) runs `infrastructure/scripts/deploy.sh <sha>`.
3. `deploy.sh`: pull images → start db/redis → `migrate` → `up -d` → HTTPS health check → on failure, restart the previous tag.

Migrations are not reversed on rollback, so keep each migration compatible with the previous release.

## API

- `GET /api/v1/health/` — public health check
- `/api/v1/auth/` — csrf, register, login, logout, me, verify-email, password-reset, password/change
- `/api/v1/organizations/`, `/members/`, `/invitations/`, `/memberships/` — workspaces and roles
- OpenAPI: `/api/v1/schema/`, Swagger UI: `/api/v1/docs/`

Authentication is a session cookie (HttpOnly) with CSRF; the SPA and API share the origin `app.mspointit.com`.
Non-members always receive 404 for another workspace's objects (tenant isolation tests in `backend/tests/`).
