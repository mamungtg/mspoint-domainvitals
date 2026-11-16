#!/usr/bin/env bash
# Nightly PostgreSQL backup for DomainVitals. Installed to /opt/domainvitals by
# deploy.sh; run by cron as the user that owns the stack (ghrunner):
#
#   /opt/domainvitals/backup.sh
#
# - Writes a compressed custom-format dump (pg_dump -Fc) to backups/daily/.
# - Sunday's dump is also kept in backups/weekly/, the 1st of the month in
#   backups/monthly/.
# - Retention: BACKUP_KEEP_DAILY (14), BACKUP_KEEP_WEEKLY (8),
#   BACKUP_KEEP_MONTHLY (12) files.
# - Offsite copy (recommended): set BACKUP_RCLONE_REMOTE in .env, e.g.
#   "b2crypt:domainvitals" (an rclone crypt remote, so the copy is encrypted).
# - Monitoring: set BACKUP_PING_URL (e.g. a healthchecks.io check); it is
#   pinged on success and /fail on failure.
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
DC="${DC:-$APP_DIR/dc}"
cd "$APP_DIR"

envval() { { grep -E "^$1=" .env 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
DB_NAME="$(envval POSTGRES_DB)"; DB_USER="$(envval POSTGRES_USER)"
: "${DB_NAME:?POSTGRES_DB missing in .env}" "${DB_USER:?POSTGRES_USER missing in .env}"
DEST="${BACKUP_DIR:-$(envval BACKUP_DIR)}"; DEST="${DEST:-$APP_DIR/backups}"
KEEP_DAILY="$(envval BACKUP_KEEP_DAILY)"; KEEP_DAILY="${KEEP_DAILY:-14}"
KEEP_WEEKLY="$(envval BACKUP_KEEP_WEEKLY)"; KEEP_WEEKLY="${KEEP_WEEKLY:-8}"
KEEP_MONTHLY="$(envval BACKUP_KEEP_MONTHLY)"; KEEP_MONTHLY="${KEEP_MONTHLY:-12}"
REMOTE="$(envval BACKUP_RCLONE_REMOTE)"
PING="$(envval BACKUP_PING_URL)"

log() { printf '[backup %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
ping_monitor() { [[ -z "$PING" ]] || curl -fsS -m 10 --retry 3 -o /dev/null "$PING$1" || true; }
fail() { log "FAILED: $*"; ping_monitor /fail; exit 1; }
trap 'fail "line $LINENO"' ERR

umask 077
mkdir -p "$DEST/daily" "$DEST/weekly" "$DEST/monthly"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
FILE="$DEST/daily/domainvitals-$STAMP.dump"
TMP="$FILE.partial"

log "dumping $DB_NAME"
"$DC" exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc -Z 6 --no-owner --no-privileges > "$TMP"
# A valid custom-format dump starts with "PGDMP" and lists its contents.
[[ "$(head -c 5 "$TMP")" == "PGDMP" ]] || fail "dump has no PGDMP header"
"$DC" exec -T db pg_restore --list < "$TMP" > /dev/null || fail "dump is not readable by pg_restore"
mv "$TMP" "$FILE"
sha256sum "$FILE" | sed "s#  .*/#  #" > "$FILE.sha256"
log "wrote $FILE ($(du -h "$FILE" | cut -f1))"

copy_to() { cp "$FILE" "$DEST/$1/"; cp "$FILE.sha256" "$DEST/$1/"; }
if [[ "$(date -u +%u)" == 7 ]]; then copy_to weekly; fi
if [[ "$(date -u +%d)" == 01 ]]; then copy_to monthly; fi

prune() {  # keep the newest N dumps in a folder
  local dir="$1" keep="$2"
  { ls -1t "$dir"/domainvitals-*.dump 2>/dev/null || true; } | tail -n +"$((keep + 1))" | while read -r old; do
    rm -f "$old" "$old.sha256"
  done
}
prune "$DEST/daily" "$KEEP_DAILY"
prune "$DEST/weekly" "$KEEP_WEEKLY"
prune "$DEST/monthly" "$KEEP_MONTHLY"

if [[ -n "$REMOTE" ]]; then
  command -v rclone >/dev/null || fail "BACKUP_RCLONE_REMOTE is set but rclone is not installed"
  log "copying to $REMOTE"
  # sync mirrors local retention to the remote, so old copies are removed there too
  rclone sync --quiet "$DEST" "$REMOTE" --include "/{daily,weekly,monthly}/domainvitals-*" || fail "offsite copy failed"
fi

trap - ERR
ping_monitor ""
log "done"
