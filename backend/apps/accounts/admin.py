from django import forms
from django.contrib import admin

from apps.accounts.models import Connection, Consent, Member
from core.adminbase import AuditedAdmin, ReadOnlyAdmin


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["role", "verification_level", "organisation"]

    def clean(self):
        data = super().clean()
        if data.get("role") == "partner_admin" and not data.get("organisation"):
            raise forms.ValidationError("A partner admin must belong to an organisation")
        return data


@admin.register(Member)
class MemberAdmin(AuditedAdmin):
    """Super admins verify members (F7) and appoint partner admins here. Everything else is read-only."""

    form = MemberForm

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

    def save_model(self, request, obj, form, change):
        if change and "organisation" in form.changed_data:
            obj.visible_to_org = False  # the member agreed to be visible to the old organisation, not the new one
        super().save_model(request, obj, form, change)


admin.site.register([Connection, Consent], ReadOnlyAdmin)
