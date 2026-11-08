from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "full_name", "email_verified", "is_active", "is_staff", "created_at"]
    search_fields = ["email", "full_name"]
    readonly_fields = ["created_at", "last_login", "email_verified_at"]
    fieldsets = (
        (None, {"fields": ("email", "password", "full_name")}),
        ("Status", {"fields": ("is_active", "email_verified", "email_verified_at", "mfa_enabled")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("created_at", "last_login")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
