from django.urls import path

from . import views

urlpatterns = [
    path("organizations/<uuid:org_id>/certificates/", views.OrgCertificatesView.as_view(), name="org-certificates"),
    path("domains/<uuid:domain_id>/tls-hosts/", views.DomainHostsView.as_view(), name="domain-tls-hosts"),
    path("tls-hosts/<uuid:host_id>/", views.HostDetailView.as_view(), name="tls-host-detail"),
    path("tls-hosts/<uuid:host_id>/scan/", views.HostScanView.as_view(), name="tls-host-scan"),
    path("tls-hosts/<uuid:host_id>/scans/", views.HostScansView.as_view(), name="tls-host-scans"),
]
