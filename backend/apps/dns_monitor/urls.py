from django.urls import path

from . import views

urlpatterns = [
    path("domains/<uuid:domain_id>/records/", views.DomainRecordsView.as_view(), name="domain-records"),
    path("domains/<uuid:domain_id>/changes/", views.DomainChangesView.as_view(), name="domain-changes"),
    path("domains/<uuid:domain_id>/propagation/", views.DomainPropagationView.as_view(), name="domain-propagation"),
    path("tools/propagation/", views.ToolPropagationView.as_view(), name="tools-propagation"),
]
