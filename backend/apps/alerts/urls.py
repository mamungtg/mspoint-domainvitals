from django.urls import path

from . import views

urlpatterns = [
    path("organizations/<uuid:org_id>/alerts/", views.OrgAlertsView.as_view(), name="org-alerts"),
    path("alerts/<uuid:alert_id>/acknowledge/", views.AlertAcknowledgeView.as_view(), name="alert-acknowledge"),
    path("organizations/<uuid:org_id>/alert-channels/", views.ChannelsView.as_view(), name="alert-channels"),
    path("alert-channels/<uuid:channel_id>/", views.ChannelDetailView.as_view(), name="alert-channel-detail"),
    path("alert-channels/<uuid:channel_id>/test/", views.ChannelTestView.as_view(), name="alert-channel-test"),
]
