from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def create_accounts(apps, schema_editor):
    """Workspaces that existed before billing start a 14-day Agency trial."""
    Organization = apps.get_model("organizations", "Organization")
    BillingAccount = apps.get_model("billing", "BillingAccount")
    ends = timezone.now() + timedelta(days=14)
    for org in Organization.objects.filter(is_demo=False):
        BillingAccount.objects.get_or_create(
            organization=org, defaults={"plan": "agency", "status": "trialing", "trial_ends_at": ends}
        )


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial"), ("organizations", "0002_alter_organization_options_organization_is_demo")]
    operations = [migrations.RunPython(create_accounts, migrations.RunPython.noop)]
