from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.organizations.models import Organization

from .models import BillingAccount


@receiver(post_save, sender=Organization)
def billing_for_new_workspace(sender, instance, created, **kwargs):
    if created and not instance.is_demo:
        BillingAccount.start_trial(instance)
