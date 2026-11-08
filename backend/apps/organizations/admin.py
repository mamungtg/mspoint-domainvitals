from django.contrib import admin

from .models import Invitation, Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    raw_id_fields = ["user"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "status", "created_at"]
    search_fields = ["name", "slug", "owner__email"]
    list_filter = ["status"]
    inlines = [MembershipInline]
    raw_id_fields = ["owner"]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "created_at", "expires_at", "accepted_at", "revoked_at"]
    search_fields = ["email", "organization__name"]
    exclude = ["token_hash"]
