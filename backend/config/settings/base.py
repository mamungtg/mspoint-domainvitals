"""Base settings shared by all environments.

All secrets and environment-specific values come from environment variables
(see .env.example at the repository root). Nothing secret is committed.
"""

from datetime import timedelta  # noqa: F401  (kept for future token lifetimes)
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DJANGO_CORS_ALLOWED_ORIGINS=(list, []),
)
# Optional .env file for local development only.
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    # Local
    "apps.accounts",
    "apps.organizations",
    "apps.audit",
    "apps.domains",
    "apps.dns_monitor",
]

MIDDLEWARE = [
    "common.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", 60)

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Sessions, cookies, CSRF -------------------------------------------------
# The SPA is served from the same origin as /api/ (Nginx proxies /api/ on
# app.mspointit.com), so session cookies stay first-party and HttpOnly.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 7)
SESSION_COOKIE_NAME = "dv_session"
CSRF_COOKIE_NAME = "dv_csrftoken"
CSRF_COOKIE_HTTPONLY = False  # SPA reads it to send X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env("DJANGO_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# --- REST framework ----------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.envelope_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": env("THROTTLE_LOGIN", default="10/min"),
        "register": env("THROTTLE_REGISTER", default="5/hour"),
        "password_reset": env("THROTTLE_PASSWORD_RESET", default="5/hour"),
        "verify_email": env("THROTTLE_VERIFY_EMAIL", default="20/hour"),
        "invite": env("THROTTLE_INVITE", default="30/hour"),
        "tools": env("THROTTLE_TOOLS", default="30/hour"),
        "domain_write": env("THROTTLE_DOMAIN_WRITE", default="60/hour"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MSPoint DomainVitals API",
    "DESCRIPTION": "Email authentication, DNS and SSL/TLS monitoring API.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Cache / Redis / Celery --------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 120
CELERY_TASK_SOFT_TIME_LIMIT = 90
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "dns-scan-due-domains": {"task": "apps.dns_monitor.tasks.schedule_due_scans", "schedule": 15 * 60},
    "recheck-domain-verification": {"task": "apps.dns_monitor.tasks.recheck_verifications", "schedule": 6 * 60 * 60},
}

# --- DNS monitoring ----------------------------------------------------------
DNS_RESOLVERS = env.list("DNS_RESOLVERS", default=["1.1.1.1", "8.8.8.8", "9.9.9.9"])
DNS_SCAN_INTERVAL_HOURS = env.int("DNS_SCAN_INTERVAL_HOURS", 24)
DNS_MANUAL_SCAN_COOLDOWN_SECONDS = env.int("DNS_MANUAL_SCAN_COOLDOWN_SECONDS", 60)
DOMAIN_LIMIT_PER_ORG = env.int("DOMAIN_LIMIT_PER_ORG", 100)
VERIFICATION_GRACE_HOURS = env.int("VERIFICATION_GRACE_HOURS", 72)

# --- Email -------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="DomainVitals <no-reply@mspointit.com>")

# Public URL of the SPA, used to build links in emails.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173").rstrip("/")

# Lifetimes
EMAIL_VERIFICATION_MAX_AGE = env.int("EMAIL_VERIFICATION_MAX_AGE", 60 * 60 * 48)
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", 60 * 60 * 2)
INVITATION_MAX_AGE_DAYS = env.int("INVITATION_MAX_AGE_DAYS", 7)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "common.middleware.RequestIDLogFilter"}},
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain", "filters": ["request_id"]},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

ENABLE_ADMIN = env.bool("ENABLE_ADMIN", False)
