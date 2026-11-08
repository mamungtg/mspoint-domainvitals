from rest_framework.authentication import SessionAuthentication


def enforce_csrf(request):
    """Enforce CSRF on anonymous, state-changing endpoints (login, register...).

    DRF only enforces CSRF for authenticated session requests; login CSRF is a
    real attack, so anonymous POST endpoints call this explicitly.
    """
    SessionAuthentication().enforce_csrf(request)
