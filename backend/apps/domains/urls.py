from django.urls import path

from . import views

urlpatterns = [
    path("organizations/demo/", views.DemoWorkspaceView.as_view(), name="org-demo"),
    path("organizations/<uuid:org_id>/domains/", views.OrgDomainsView.as_view(), name="org-domains"),
    path("organizations/<uuid:org_id>/overview/", views.OverviewView.as_view(), name="org-overview"),
    path("domains/<uuid:domain_id>/", views.DomainDetailView.as_view(), name="domain-detail"),
    path("domains/<uuid:domain_id>/verify/", views.DomainVerifyView.as_view(), name="domain-verify"),
    path("domains/<uuid:domain_id>/scan/", views.DomainScanView.as_view(), name="domain-scan"),
    path("domains/<uuid:domain_id>/scans/", views.DomainScansView.as_view(), name="domain-scans"),
    path("scans/<uuid:scan_id>/", views.ScanDetailView.as_view(), name="scan-detail"),
    path("tools/check/", views.ToolCheckView.as_view(), name="tools-check"),
]
