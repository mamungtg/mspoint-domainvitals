from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1"]  # noqa: F405
CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS or ["http://localhost:5173"]  # noqa: F405
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")  # noqa: F405
EMAIL_FILE_PATH = env("EMAIL_FILE_PATH", default=str(BASE_DIR / ".mail"))  # noqa: F405
# Run Celery tasks inline when no worker is running locally.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", False)  # noqa: F405
