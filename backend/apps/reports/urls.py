from django.urls import path

from . import views

urlpatterns = [
    path("organizations/<uuid:org_id>/reports/pdf/", views.ReportPdfView.as_view(), name="report-pdf"),
    path("organizations/<uuid:org_id>/reports/branding/", views.BrandingView.as_view(), name="report-branding"),
    path("organizations/<uuid:org_id>/reports/branding/logo/", views.LogoView.as_view(), name="report-logo"),
    path("organizations/<uuid:org_id>/reports/schedule/", views.ScheduleView.as_view(), name="report-schedule"),
]
