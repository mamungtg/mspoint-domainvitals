from rest_framework.authentication import SessionAuthentication


def enforce_csrf(request):
    """Enforce CSRF on anonymous, state-changing endpoints (login, register...).

    DRF only enforces CSRF for authenticated session requests; login CSRF is a
    real attack, so anonymous POST endpoints call this explicitly.
    """
    SessionAuthentication().enforce_csrf(request)


class VerifiedSessionAuthentication(SessionAuthentication):
    """Session auth that only accepts users who confirmed their email address.

    Login already refuses unverified accounts; this also closes sessions that
    were opened before verification became mandatory.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, auth = result
        if not getattr(user, "email_verified", False):
            return None
        return user, auth
