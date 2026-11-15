from django.apps import AppConfig


class AlertsConfig(AppConfig):
    name = "apps.alerts"
    label = "alerts"
    verbose_name = "Alerts and notifications"

    def ready(self):
        from . import signals  # noqa: F401
