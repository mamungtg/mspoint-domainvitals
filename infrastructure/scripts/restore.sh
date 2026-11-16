#!/usr/bin/env bash
# DISASTER RECOVERY: replace the live database with a backup.
#
#   /opt/domainvitals/restore.sh <dump-file> --yes-replace-live-data
#
# Stops the app, takes a safety dump of the current database, recreates the
# database from <dump-file>, runs migrations and starts the app again.
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
DC="${DC:-$APP_DIR/dc}"
cd "$APP_DIR"

FILE="${1:?usage: restore.sh <dump-file> --yes-replace-live-data}"
[[ "${2:-}" == "--yes-replace-live-data" ]] || { echo "Refusing: add --yes-replace-live-data to confirm." >&2; exit 2; }
[[ -f "$FILE" ]] || { echo "No such file: $FILE" >&2; exit 1; }

envval() { { grep -E "^$1=" .env 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
DB_NAME="$(envval POSTGRES_DB)"; DB_USER="$(envval POSTGRES_USER)"
log() { printf '[restore %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
psql_db() { "$DC" exec -T db psql -v ON_ERROR_STOP=1 -X -q -U "$DB_USER" "$@"; }

"$DC" exec -T db pg_restore --list < "$FILE" > /dev/null || { log "not a valid dump: $FILE"; exit 1; }

log "stopping the app"
"$DC" stop web beat worker backend

mkdir -p backups/pre-restore
SAFETY="backups/pre-restore/domainvitals-$(date -u +%Y%m%d-%H%M%S).dump"
log "safety copy of the current database -> $SAFETY"
(umask 077; "$DC" exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$SAFETY")

log "recreating $DB_NAME from $FILE"
psql_db -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid()" >/dev/null
psql_db -d postgres -c "DROP DATABASE \"$DB_NAME\"" -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\""
"$DC" exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges --exit-on-error < "$FILE"

log "migrating and starting the app"
"$DC" run --rm --no-deps backend python manage.py migrate --noinput
"$DC" up -d
log "done. If anything is wrong, restore $SAFETY the same way."
