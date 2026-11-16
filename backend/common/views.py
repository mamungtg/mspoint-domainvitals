import logging
import uuid

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import health as jobs

logger = logging.getLogger(__name__)


def _database() -> str:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return "ok"
    except Exception:
        logger.exception("health: database check failed")
        return "error"


def _cache() -> str:
    key = f"health:probe:{uuid.uuid4().hex}"
    try:
        cache.set(key, 1, timeout=10)
        ok = cache.get(key) == 1
        cache.delete(key)
        return "ok" if ok else "error"
    except Exception:
        logger.exception("health: redis check failed")
        return "error"


def _respond(checks: dict, extra: dict | None = None) -> Response:
    healthy = all(v == "ok" for v in checks.values())
    body = {"status": "ok" if healthy else "degraded", "checks": checks, **(extra or {})}
    return Response(body, status=200 if healthy else 503)


@extend_schema(responses={200: dict, 503: dict}, tags=["health"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    """Readiness probe used by deploys: the web app, database and Redis."""
    return _respond({"database": _database(), "redis": _cache()})


@extend_schema(responses={200: dict, 503: dict}, tags=["health"])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health_deep(request):
    """For external uptime monitors: also fails when background jobs stop.

    Reports only states and ages, never hostnames or errors.
    """
    checks = {"database": _database(), "redis": _cache()}
    ages = {}
    for name in jobs.MAX_AGE:
        st = jobs.status(name)
        if st["status"] == "disabled":
            continue
        checks[name] = st["status"]
        ages[name] = st["age"]
    return _respond(checks, {"last_run_seconds_ago": ages})
