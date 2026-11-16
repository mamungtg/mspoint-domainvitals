#!/usr/bin/env bash
# Proves the newest backup can be restored. Restores it into a scratch
# database inside the running db container, checks that the main tables have
# rows, then drops the scratch database. Live data is not touched.
#
#   /opt/domainvitals/restore-test.sh [dump-file]
#
# Run weekly from cron. Set RESTORE_TEST_PING_URL in .env to get alerted when
# it fails.
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
DC="${DC:-$APP_DIR/dc}"
cd "$APP_DIR"

envval() { { grep -E "^$1=" .env 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
DB_NAME="$(envval POSTGRES_DB)"; DB_USER="$(envval POSTGRES_USER)"
DEST="${BACKUP_DIR:-$(envval BACKUP_DIR)}"; DEST="${DEST:-$APP_DIR/backups}"
PING="$(envval RESTORE_TEST_PING_URL)"
SCRATCH="dv_restore_test"

log() { printf '[restore-test %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
ping_monitor() { [[ -z "$PING" ]] || curl -fsS -m 10 --retry 3 -o /dev/null "$PING$1" || true; }
psql_db() { "$DC" exec -T db psql -v ON_ERROR_STOP=1 -X -q -U "$DB_USER" "$@"; }
cleanup() { psql_db -d postgres -c "DROP DATABASE IF EXISTS $SCRATCH" >/dev/null 2>&1 || true; }
fail() { log "FAILED: $*"; cleanup; ping_monitor /fail; exit 1; }
trap 'fail "line $LINENO"' ERR

FILE="${1:-$(ls -1t "$DEST"/daily/domainvitals-*.dump 2>/dev/null | head -1 || true)}"
[[ -n "$FILE" && -f "$FILE" ]] || fail "no backup found in $DEST/daily"
if [[ -f "$FILE.sha256" ]]; then
  (cd "$(dirname "$FILE")" && sha256sum -c --quiet "$(basename "$FILE").sha256") || fail "checksum mismatch for $FILE"
fi
AGE_H=$(( ($(date +%s) - $(stat -c %Y "$FILE")) / 3600 ))
log "testing $(basename "$FILE") (${AGE_H}h old)"
[[ $AGE_H -le 48 ]] || log "WARNING: newest backup is older than 48 hours"

cleanup
psql_db -d postgres -c "CREATE DATABASE $SCRATCH" >/dev/null
"$DC" exec -T db pg_restore -U "$DB_USER" -d "$SCRATCH" --no-owner --no-privileges --exit-on-error < "$FILE"

count() { psql_db -d "$SCRATCH" -tA -c "SELECT count(*) FROM $1"; }
MIGRATIONS=$(count django_migrations)
USERS=$(count accounts_user)
ORGS=$(count organizations_organization)
DOMAINS=$(count domains_domain)
log "restored: $MIGRATIONS migrations, $USERS users, $ORGS workspaces, $DOMAINS domains"
[[ "$MIGRATIONS" -gt 0 ]] || fail "no migrations in the restored database"
[[ "$USERS" -gt 0 ]] || fail "no users in the restored database"

# Compare with live data: the backup should not have lost most of the users.
LIVE_USERS=$(psql_db -d "$DB_NAME" -tA -c "SELECT count(*) FROM accounts_user")
[[ $((USERS * 2)) -ge "$LIVE_USERS" ]] || fail "backup has $USERS users, live has $LIVE_USERS"

cleanup
trap - ERR
ping_monitor ""
log "OK"
