#!/usr/bin/env bash
# Deploy a given image tag on this server. Run by the self-hosted GitHub
# Actions runner (deploy.yml) from the repository checkout.
#
#   infrastructure/scripts/deploy.sh <image-tag>
#
# Requires: /opt/domainvitals/.env and /opt/domainvitals/certs/origin.{pem,key}
# Rollback: on failed health check the previous tag is started again.
# NOTE: database migrations are NOT reversed on rollback, so every migration
# must stay compatible with the previous release (expand -> deploy -> contract).
set -euo pipefail

TAG="${1:?usage: deploy.sh <image-tag>}"
APP_DIR="${APP_DIR:-/opt/domainvitals}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
: "${IMAGE_PREFIX:?IMAGE_PREFIX must be set, e.g. ghcr.io/owner/domainvitals}"
HEALTH_HOST="${HEALTH_HOST:-app.mspointit.com}"

log() { printf '[deploy %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

[[ -f "$APP_DIR/.env" ]] || { log "missing $APP_DIR/.env"; exit 1; }
[[ -f "$APP_DIR/certs/origin.pem" && -f "$APP_DIR/certs/origin.key" ]] || { log "missing origin certificate in $APP_DIR/certs"; exit 1; }

install -m 0644 "$REPO_DIR/docker-compose.prod.yml" "$APP_DIR/docker-compose.yml"
cd "$APP_DIR"

PREV_TAG="$(cat .current_tag 2>/dev/null || true)"
export IMAGE_PREFIX
compose() { IMAGE_TAG="$1" docker compose -f docker-compose.yml "${@:2}"; }

healthy() {
  for _ in $(seq 1 45); do
    if curl -fsk --max-time 5 --resolve "$HEALTH_HOST:443:127.0.0.1" "https://$HEALTH_HOST/api/v1/health/" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

log "deploying $TAG (previous: ${PREV_TAG:-none})"
[[ "${SKIP_PULL:-0}" == 1 ]] || compose "$TAG" pull --quiet  # SKIP_PULL=1 only for local testing
# --wait blocks until db/redis report healthy (first boot of Postgres
# initialises the cluster and restarts once, which takes a few seconds).
compose "$TAG" up -d --wait --wait-timeout 120 db redis
log "running migrations"
for attempt in 1 2 3 4 5; do
  if compose "$TAG" run --rm --no-deps backend python manage.py migrate --noinput; then
    break
  fi
  if [[ $attempt -eq 5 ]]; then log "migrations failed after $attempt attempts"; exit 1; fi
  log "migrate attempt $attempt failed; retrying in 5s"
  sleep 5
done
compose "$TAG" up -d --remove-orphans

if healthy; then
  echo "$TAG" > .current_tag
  log "healthy; $TAG is live"
  docker image prune -af --filter "until=168h" >/dev/null || true
  exit 0
fi

log "health check FAILED for $TAG"
compose "$TAG" ps || true
compose "$TAG" logs --tail=80 backend web || true
if [[ -n "$PREV_TAG" ]]; then
  log "rolling back to $PREV_TAG"
  compose "$PREV_TAG" up -d --remove-orphans
  if healthy; then log "rollback healthy"; else log "rollback ALSO unhealthy - manual action needed"; fi
fi
exit 1
