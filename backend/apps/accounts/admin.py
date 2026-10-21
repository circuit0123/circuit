from django.contrib import admin

from apps.accounts.models import Connection, Consent, Member
from core.adminbase import AuditedAdmin, ReadOnlyAdmin


@admin.register(Member)
class MemberAdmin(AuditedAdmin):
    """Super admins verify members here (F7). Only verification and role-adjacent fields are editable."""

    list_display = ("id", "display_name", "role", "verification_level", "organisation", "city")
    list_filter = ("role", "verification_level", "organisation")
    search_fields = ("display_name",)
    readonly_fields = [
        "auth_user_id",
        "display_name",
        "bio",
        "location",
        "city",
        "college",
        "organisation",
        "open_intro_slots",
        "circuits_opt_in",
        "is_minor",
        "profile_visibility",
        "visible_to_org",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False


admin.site.register([Connection, Consent], ReadOnlyAdmin)
