# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

COPY requirements/ requirements/
RUN pip install -r requirements/prod.txt

COPY . .
# collectstatic needs settings to import; use throwaway values at build time only.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod DJANGO_SECRET_KEY=build-only \
    DATABASE_URL=sqlite:////tmp/build.db python manage.py collectstatic --noinput \
    && rm -f /tmp/build.db && chown -R app:app /app

USER app
EXPOSE 8000
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/', timeout=4)" || exit 1
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", \
     "--access-logfile", "-", "--forwarded-allow-ips", "*"]
