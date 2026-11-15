from django.db import migrations


def create_defaults(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Channel = apps.get_model("alerts", "Channel")
    import secrets

    for org in Organization.objects.filter(is_demo=False):
        if not Channel.objects.filter(organization=org).exists():
            Channel.objects.create(
                organization=org,
                type="email",
                name="Owners and admins",
                notify_managers=True,
                events=["check", "certificate", "dns_change", "dmarc_sender"],
                min_severity="warning",
                secret=secrets.token_hex(32),
            )


class Migration(migrations.Migration):
    dependencies = [("alerts", "0001_initial"), ("organizations", "0002_alter_organization_options_organization_is_demo")]
    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]
