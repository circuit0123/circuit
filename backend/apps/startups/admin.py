from django.contrib import admin

from apps.startups.models import ClaimRequest, Startup, StartupInterest, StartupMember, StartupTrait
from core.adminbase import AuditedAdmin, ReadOnlyAdmin


@admin.register(Startup)
class StartupAdmin(AuditedAdmin):
    """Review crawled startups and handle takedowns (F13)."""

    list_display = ("id", "name", "website_domain", "sector", "hiring", "source", "confidence", "claimed_by")
    list_filter = ("source", "hiring", "sector")
    search_fields = ("name", "website_domain")
    readonly_fields = ("claimed_by", "claimed_at", "view_count")


admin.site.register([ClaimRequest, StartupInterest, StartupMember, StartupTrait], ReadOnlyAdmin)
