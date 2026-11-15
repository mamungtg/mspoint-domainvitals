from django.core.management.base import BaseCommand, CommandError

from apps.billing import stripe_api
from apps.billing.plans import PAID, PLANS, lookup_key


class Command(BaseCommand):
    help = "Create the DomainVitals products, prices and customer portal settings in Stripe (safe to run again)."

    def handle(self, **options):
        try:
            s = stripe_api.client()
        except stripe_api.BillingNotConfigured as e:
            raise CommandError(f"{e} Set STRIPE_SECRET_KEY first.") from None
        mode = "TEST" if s.api_key.startswith(("sk_test", "rk_test")) else "LIVE"
        self.stdout.write(f"Stripe mode: {mode}")
        products = {}
        for plan in PAID:
            p = PLANS[plan]
            found = s.Product.search(query=f"metadata['dv_plan']:'{plan}'", limit=1).data
            prod = (
                found[0]
                if found
                else s.Product.create(
                    name=f"DomainVitals {p['name']}",
                    description=p["summary"],
                    metadata={"dv_plan": plan},
                    idempotency_key=f"dv-product-{plan}",
                )
            )
            products[plan] = prod.id
            for interval in ("month", "year"):
                key = lookup_key(plan, interval)
                if s.Price.list(lookup_keys=[key], active=True, limit=1).data:
                    self.stdout.write(f"  {key}: exists")
                    continue
                s.Price.create(
                    product=prod.id,
                    currency="usd",
                    unit_amount=p["price"][interval] * 100,
                    recurring={"interval": interval},
                    lookup_key=key,
                    tax_behavior="exclusive",
                    metadata={"dv_plan": plan},
                )
                self.stdout.write(self.style.SUCCESS(f"  {key}: created (${p['price'][interval]}/{interval})"))

        configs = [
            c
            for c in s.billing_portal.Configuration.list(active=True, limit=20).data
            if (c.metadata or {}).get("dv") == "1"
        ]
        prices_by_product = [
            {
                "product": products[plan],
                "prices": [
                    s.Price.list(lookup_keys=[lookup_key(plan, i)], limit=1).data[0].id for i in ("month", "year")
                ],
            }
            for plan in PAID
        ]
        features = {
            "customer_update": {"enabled": True, "allowed_updates": ["email", "address", "tax_id", "name"]},
            "invoice_history": {"enabled": True},
            "payment_method_update": {"enabled": True},
            "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
            "subscription_update": {
                "enabled": True,
                "default_allowed_updates": ["price"],
                "proration_behavior": "create_prorations",
                "products": prices_by_product,
            },
        }
        business = {"headline": "DomainVitals by MSPoint: manage your subscription"}
        if configs:
            s.billing_portal.Configuration.modify(configs[0].id, features=features, business_profile=business)
            self.stdout.write("Customer portal: updated")
        else:
            s.billing_portal.Configuration.create(features=features, business_profile=business, metadata={"dv": "1"})
            self.stdout.write(self.style.SUCCESS("Customer portal: created"))
        self.stdout.write(self.style.SUCCESS("Done."))
