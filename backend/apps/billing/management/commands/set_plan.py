from django.core.management.base import BaseCommand, CommandError

from apps.billing.models import BillingAccount
from apps.billing.plans import PLANS
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Set a workspace's plan by hand (Enterprise contracts, support). Stripe subscriptions override this on their next event."

    def add_arguments(self, parser):
        parser.add_argument("workspace", help="Workspace ID or exact name")
        parser.add_argument("plan", choices=list(PLANS))
        parser.add_argument("--domains", type=int, help="Custom domain limit")
        parser.add_argument("--members", type=int, help="Custom member limit (omit for the plan default)")

    def handle(self, workspace, plan, domains=None, members=None, **options):
        org = Organization.objects.filter(pk=workspace).first() if len(workspace) == 36 else None
        org = org or Organization.objects.filter(name=workspace, is_demo=False).first()
        if org is None:
            raise CommandError(f"No workspace {workspace!r}.")
        acc, _ = BillingAccount.objects.get_or_create(organization=org)
        acc.plan, acc.status, acc.trial_ends_at = (
            plan,
            (BillingAccount.Status.FREE if plan == "free" else BillingAccount.Status.ACTIVE),
            None,
        )
        acc.custom_limits = {k: v for k, v in {"domains": domains, "members": members}.items() if v is not None}
        acc.save()
        self.stdout.write(self.style.SUCCESS(f"{org.name}: {PLANS[plan]['name']} {acc.limits()}"))
