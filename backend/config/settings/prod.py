from .base import *  # noqa: F403

DEBUG = False

# TLS terminates at Nginx (behind Cloudflare). Trust the forwarded proto header
# set by Nginx only.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = False  # enable only after every subdomain serves HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/(deep/)?$"]

if SENTRY_DSN:  # noqa: F405
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,  # noqa: F405
        environment=SENTRY_ENVIRONMENT,  # noqa: F405
        release=env("IMAGE_TAG", default=None),  # noqa: F405
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,  # noqa: F405
        send_default_pii=False,
    )
