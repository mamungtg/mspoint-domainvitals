#!/usr/bin/env bash
# CI test for backup.sh / restore-test.sh / restore.sh against a local
# PostgreSQL (PGHOST, PGUSER). A shim replaces ./dc so "dc exec -T db CMD" runs
# CMD locally.
set -Eeuo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
DB=dv_backup_ci
cp "$SRC"/{backup,restore-test,restore}.sh "$WORK/"
cd "$WORK"
printf 'POSTGRES_DB=%s\nPOSTGRES_USER=%s\nBACKUP_KEEP_DAILY=2\n' "$DB" "${PGUSER:-postgres}" > .env
cat > dc <<'S'
#!/usr/bin/env bash
if [[ "$1" == exec ]]; then shift 3; exec "$@"; fi
echo "dc $*" >> dc.log
S
chmod +x dc

psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $DB" -c "CREATE DATABASE $DB"
psql -X -q -d "$DB" <<'SQL'
CREATE TABLE django_migrations (id int);           INSERT INTO django_migrations VALUES (1);
CREATE TABLE accounts_user (id int);               INSERT INTO accounts_user VALUES (1), (2);
CREATE TABLE organizations_organization (id int);  INSERT INTO organizations_organization VALUES (1);
CREATE TABLE domains_domain (id int);              INSERT INTO domains_domain VALUES (1);
SQL

for _ in 1 2 3; do ./backup.sh; sleep 1.1; done
[[ $(ls backups/daily/*.dump | wc -l) == 2 ]] || { echo "retention not applied"; exit 1; }
./restore-test.sh

psql -X -q -d "$DB" -c "DELETE FROM domains_domain"
./restore.sh "$(ls -t backups/daily/*.dump | head -1)" --yes-replace-live-data
[[ $(psql -X -tA -d "$DB" -c "SELECT count(*) FROM domains_domain") == 1 ]] || { echo "restore did not bring data back"; exit 1; }

if ./restore.sh backups/daily/x.dump 2>/dev/null; then echo "restore ran without confirmation"; exit 1; fi
f="$(ls -t backups/daily/*.dump | head -1)"; printf x >> "$f"
if ./restore-test.sh "$f"; then echo "corrupt backup passed"; exit 1; fi
psql -X -q -d postgres -c "DROP DATABASE $DB"
echo "backup scripts: all checks passed"
