from django.urls import path

from . import views

urlpatterns = [
    path("organizations/", views.OrganizationListCreateView.as_view(), name="org-list"),
    path("organizations/<uuid:org_id>/", views.OrganizationDetailView.as_view(), name="org-detail"),
    path("organizations/<uuid:org_id>/members/", views.MemberListInviteView.as_view(), name="org-members"),
    path("organizations/<uuid:org_id>/invitations/", views.InvitationListView.as_view(), name="org-invitations"),
    path("invitations/<uuid:invitation_id>/", views.InvitationRevokeView.as_view(), name="invitation-revoke"),
    path("invitations/accept/", views.InvitationAcceptView.as_view(), name="invitation-accept"),
    path("memberships/<uuid:membership_id>/", views.MembershipDetailView.as_view(), name="membership-detail"),
]
