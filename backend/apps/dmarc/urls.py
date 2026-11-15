from django.urls import path

from . import views

urlpatterns = [
    path("organizations/<uuid:org_id>/dmarc/", views.OrgDmarcView.as_view(), name="org-dmarc"),
    path("domains/<uuid:domain_id>/dmarc/", views.DomainDmarcView.as_view(), name="domain-dmarc"),
    path("domains/<uuid:domain_id>/dmarc/upload/", views.DmarcUploadView.as_view(), name="domain-dmarc-upload"),
]
