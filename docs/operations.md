# Operations

## How a release reaches production

1. Push to `main`. The CI workflow runs lint, migration check, backend tests and the frontend build.
2. The deploy workflow builds `ghcr.io/mamungtg/domainvitals-backend:<sha>` and `-web:<sha>`, then runs `infrastructure/scripts/deploy.sh` on the self-hosted runner (label `domainvitals`, environment `production`).
3. `deploy.sh` pulls the images, starts the database and waits for it to be healthy, runs migrations with retries, starts the rest, and checks `/api/v1/health/`. If the health check fails it rolls back to the tag in `.current_tag`.

## Everyday commands (on the server, in `/opt/domainvitals`)

| Task | Command |
| --- | --- |
| Status | `./dc ps` |
| Logs | `./dc logs -f backend worker` |
| Django shell | `./dc exec backend python manage.py shell` |
| Run migrations by hand | `./dc exec backend python manage.py migrate` |
| Restart a service | `./dc restart worker` |

`dc` loads `.env` and `.deploy.env` (image prefix and current tag) so manual compose commands use the deployed images.

## Rollback

Set `TAG` in `.deploy.env` to an earlier commit SHA and run `./dc up -d`. Migrations are forward-only; a release that changes the schema must stay compatible with the previous code for one release.

## Secrets

Secrets live only in the server's `.env` and in GitHub environment secrets. Never commit them, and never paste private keys or tunnel tokens into chats or tickets.
