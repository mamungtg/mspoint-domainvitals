from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = "apps.billing"
    label = "billing"
    verbose_name = "Plans and billing"

    def ready(self):
        from . import signals  # noqa: F401
