"""Base for the free public tools: open to everyone, with a stricter per-IP
limit for visitors who are not signed in, and CSRF checks for them too."""

from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView


def _enforce_csrf(request):
    def dummy_get_response(request):  # pragma: no cover - never called
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF Failed: {reason}")


class PublicToolView(APIView):
    permission_classes = [AllowAny]
    member_scope = "tools"
    public_scope = "public_tools"

    def get_throttles(self):
        authed = getattr(self.request, "user", None) and self.request.user.is_authenticated
        self.throttle_scope = self.member_scope if authed else self.public_scope
        return super().get_throttles()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_authenticated and request.method not in ("GET", "HEAD", "OPTIONS"):
            _enforce_csrf(request._request)
