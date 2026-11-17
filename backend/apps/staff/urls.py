from django.urls import path

from . import views

urlpatterns = [
    path("staff/overview/", views.OverviewView.as_view(), name="staff-overview"),
    path("staff/workspaces/", views.WorkspaceListView.as_view(), name="staff-workspaces"),
    path("staff/workspaces/<uuid:org_id>/", views.WorkspaceDetailView.as_view(), name="staff-workspace"),
    path("staff/users/", views.UserListView.as_view(), name="staff-users"),
]
