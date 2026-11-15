from django.urls import path

from . import views

urlpatterns = [
    path("organizations/<uuid:org_id>/billing/", views.BillingView.as_view(), name="billing"),
    path("organizations/<uuid:org_id>/billing/checkout/", views.CheckoutView.as_view(), name="billing-checkout"),
    path("organizations/<uuid:org_id>/billing/portal/", views.PortalView.as_view(), name="billing-portal"),
    path("billing/stripe/webhook/", views.StripeWebhookView.as_view(), name="stripe-webhook"),
]
