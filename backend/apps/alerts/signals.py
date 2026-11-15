from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.organizations.models import Organization

from .models import Channel, Kind, Severity


def create_default_channel(org) -> Channel:
    return Channel.objects.create(
        organization=org,
        type=Channel.Type.EMAIL,
        name="Owners and admins",
        notify_managers=True,
        events=[k.value for k in Kind],
        min_severity=Severity.WARNING,
    )


@receiver(post_save, sender=Organization)
def default_channel_for_new_workspace(sender, instance, created, **kwargs):
    if created and not instance.is_demo:
        create_default_channel(instance)
