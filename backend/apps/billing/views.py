import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record
from apps.organizations.models import Role
from apps.organizations.permissions import get_membership_or_404

from . import stripe_api
from .limits import account_for, monitored_domain_ids, usage
from .models import BillingAccount
from .plans import INTERVALS, PAID, PLANS
from .sync import handle_event

log = logging.getLogger(__name__)


def _owner_account(request, org_id):
    m = get_membership_or_404(request.user, org_id)
    if m.organization.is_demo:
        raise PermissionDenied("The sample workspace has no billing.")
    if m.role != Role.OWNER:
        raise PermissionDenied("Only the workspace owner can manage billing.")
    return m, account_for(m.organization)


class BillingView(APIView):
    @extend_schema(responses={200: dict}, tags=["billing"])
    def get(self, request, org_id):
        m = get_membership_or_404(request.user, org_id)
        org = m.organization
        catalogue = [
            {
                "key": k,
                "name": p["name"],
                "price": p["price"],
                "domains": p["domains"],
                "members": p["members"],
                "channels": p["channels"],
                "dmarc_days": p["dmarc_days"],
                "summary": p["summary"],
            }
            for k, p in PLANS.items()
        ]
        if org.is_demo:
            return Response({"demo": True, "plans": catalogue})
        acc = account_for(org)
        limits = acc.limits()
        verified = org.domains.filter(verified_at__isnull=False).count()
        return Response(
            {
                "demo": False,
                "plan": acc.effective_plan,
                "subscribed_plan": acc.plan,
                "status": acc.status,
                "interval": acc.interval,
                "trial_ends_at": acc.trial_ends_at.isoformat() if acc.trial_ends_at else None,
                "trial_active": acc.trial_active,
                "current_period_end": acc.current_period_end.isoformat() if acc.current_period_end else None,
                "cancel_at_period_end": acc.cancel_at_period_end,
                "has_customer": bool(acc.stripe_customer_id),
                "limits": limits,
                "usage": {**usage(org), "unmonitored_domains": max(0, verified - len(monitored_domain_ids(org)))},
                "can_manage": m.role == Role.OWNER,
                "online_payments": stripe_api.configured(),
                "plans": catalogue,
            }
        )


class CheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=PAID)
    interval = serializers.ChoiceField(choices=INTERVALS)


class CheckoutView(APIView):
    throttle_scope = "domain_write"

    @extend_schema(request=CheckoutSerializer, responses={200: dict}, tags=["billing"])
    def post(self, request, org_id):
        m, acc = _owner_account(request, org_id)
        ser = CheckoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if acc.status in (BillingAccount.Status.ACTIVE, BillingAccount.Status.PAST_DUE) and acc.stripe_subscription_id:
            raise ValidationError(
                {"detail": ["You already have a subscription. Use Manage billing to change the plan."]}
            )
        try:
            url = stripe_api.checkout_url(
                acc, ser.validated_data["plan"], ser.validated_data["interval"], request.user.email
            )
        except stripe_api.BillingNotConfigured as e:
            raise ValidationError({"detail": [str(e)]}) from None
        except Exception:
            log.exception("stripe checkout failed")
            raise ValidationError(
                {"detail": ["The payment page could not be opened. Please try again in a minute."]}
            ) from None
        record(
            request,
            "billing.checkout_started",
            obj=m.organization,
            organization=m.organization,
            metadata=ser.validated_data,
        )
        return Response({"url": url})


class PortalView(APIView):
    throttle_scope = "domain_write"

    @extend_schema(request=None, responses={200: dict}, tags=["billing"])
    def post(self, request, org_id):
        _, acc = _owner_account(request, org_id)
        if not acc.stripe_customer_id:
            raise ValidationError({"detail": ["There is no billing account yet. Choose a plan first."]})
        try:
            url = stripe_api.portal_url(acc)
        except stripe_api.BillingNotConfigured as e:
            raise ValidationError({"detail": [str(e)]}) from None
        except Exception:
            log.exception("stripe portal failed")
            raise ValidationError(
                {"detail": ["The billing portal could not be opened. Please try again in a minute."]}
            ) from None
        return Response({"url": url})


class StripeWebhookView(APIView):
    """Stripe -> us. Authenticated by the Stripe-Signature header, not a session."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(self, request):
        if not settings.STRIPE_WEBHOOK_SECRET:
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            event = stripe_api.construct_event(request.body, request.headers.get("Stripe-Signature", ""))
        except Exception:
            log.warning("stripe webhook with an invalid signature")
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            outcome = handle_event(event)
        except Exception:
            log.exception("stripe webhook %s failed", event.get("id"))
            from .models import StripeEvent

            StripeEvent.objects.filter(id=event["id"]).delete()  # let Stripe retry
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        log.info("stripe %s %s: %s", event["type"], event["id"], outcome)
        return Response({"ok": True})
