from django.contrib import admin

from .models import Domain


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "verified_at", "monitoring_enabled", "created_at"]
    search_fields = ["name", "organization__name"]
    list_filter = ["monitoring_enabled"]
    raw_id_fields = ["organization", "added_by", "latest_scan"]
