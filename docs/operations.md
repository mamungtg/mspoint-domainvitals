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
| Send a test email | `./dc exec backend python manage.py sendtestemail you@example.com` |
| Confirm a user by hand (support) | `./dc exec backend python manage.py verify_user user@example.com` |
| Stripe products, prices and portal | `./dc exec backend python manage.py stripe_setup` |
| Give a workspace a plan by hand | `./dc exec backend python manage.py set_plan "<workspace>" enterprise` |
| Set a user's password | `./dc exec backend python manage.py changepassword user@example.com` |

`dc` loads `.env` and `.deploy.env` (image prefix and current tag) so manual compose commands use the deployed images.

## Rollback

Set `TAG` in `.deploy.env` to an earlier commit SHA and run `./dc up -d`. Migrations are forward-only; a release that changes the schema must stay compatible with the previous code for one release.

## Backups

The database is the only state that matters; Redis holds queues and caches only.

| Script (in `/opt/domainvitals`) | What it does |
| --- | --- |
| `backup.sh` | Writes a compressed `pg_dump -Fc` to `backups/daily/` and checks it can be read. Sunday's dump is also copied to `weekly/` and the 1st of the month to `monthly/`. Keeps 14 daily, 8 weekly and 12 monthly dumps. Optionally copies them offsite with rclone (`BACKUP_RCLONE_REMOTE`). |
| `restore-test.sh` | Restores the newest dump into a scratch database, checks row counts against live, and drops it. Live data is not touched. |
| `restore.sh <file> --yes-replace-live-data` | Disaster recovery: stops the app, saves a safety dump, recreates the database from `<file>`, migrates and starts the app. |

Cron (as the user that runs the stack):

```
15 2 * * *  /opt/domainvitals/backup.sh       >> /opt/domainvitals/backups/backup.log 2>&1
45 3 * * 1  /opt/domainvitals/restore-test.sh >> /opt/domainvitals/backups/backup.log 2>&1
```

- Set `BACKUP_PING_URL` and `RESTORE_TEST_PING_URL` to healthchecks.io checks, so a backup that silently stops running is noticed.
- Keep a copy of `.env` and `certs/` in a password manager. They are not in the backups.
- CI runs all three scripts against PostgreSQL on every change (`test-backups.sh`).

## Monitoring

| Endpoint | Checks | Use |
| --- | --- | --- |
| `/api/v1/health/` | web app, database, Redis | deploy health check |
| `/api/v1/health/deep/` | the above, plus the Celery scheduler and worker (5-minute heartbeat, stale after 15 minutes) and the DMARC mailbox (stale after 1 hour, when configured) | external uptime monitor; 503 when anything is wrong |

- Point an uptime monitor (UptimeRobot, Better Stack, etc.) at `https://app.mspointit.com/api/v1/health/deep/`, every 5 minutes.
- Errors: set `SENTRY_DSN` to send them to Sentry (no personal data is sent). Otherwise set `ERROR_EMAILS` to get 500 errors by email.

## Secrets

Secrets live only in the server's `.env` and in GitHub environment secrets. Never commit them, and never paste private keys or tunnel tokens into chats or tickets.
