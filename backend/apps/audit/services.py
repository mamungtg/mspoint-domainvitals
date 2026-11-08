from common.middleware import get_request_id

from .models import AuditLog


def client_ip(request) -> str | None:
    # Nginx sets X-Real-IP from the Cloudflare-restored client address; never
    # trust a raw X-Forwarded-For chain from the internet.
    ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")
    return ip or None


def record(request, action, *, obj=None, organization=None, user=None, metadata=None):
    actor = user
    if actor is None and request is not None:
        u = getattr(request, "user", None)
        actor = u if (u is not None and u.is_authenticated) else None
    return AuditLog.objects.create(
        organization=organization,
        user=actor,
        action=action,
        object_type=obj._meta.label_lower if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
        metadata=metadata or {},
        ip_address=client_ip(request) if request is not None else None,
        request_id=get_request_id(),
    )
