from django import forms
from django.contrib import admin
from django.utils import timezone

from apps.accounts.models import Connection, ConnectionRequest, Consent, Member
from core.adminbase import AuditedAdmin, ReadOnlyAdmin, audit


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["role", "verification_level", "organisation", "suspended_at"]

    def clean(self):
        data = super().clean()
        if data.get("role") == "partner_admin" and not data.get("organisation"):
            raise forms.ValidationError("A partner admin must belong to an organisation")
        return data


@admin.register(Member)
class MemberAdmin(AuditedAdmin):
    """Super admins verify members (F7) and appoint partner admins here. Everything else is read-only."""

    form = MemberForm

    list_display = ("id", "display_name", "role", "verification_level", "organisation", "city", "suspended_at")
    list_filter = ("role", "verification_level", "organisation", "suspended_at")
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

    actions = ["suspend_members", "reinstate_members"]

    @admin.action(description="Suspend selected members (locked out of the API at once)")
    def suspend_members(self, request, queryset):
        n = 0
        for m in queryset.filter(suspended_at__isnull=True):
            m.suspended_at = timezone.now()
            m.visible_to_org = False
            m.save(update_fields=["suspended_at", "visible_to_org", "updated_at"])
            audit(request, "suspend", m)
            n += 1
        self.message_user(request, f"Suspended {n} member(s)")

    @admin.action(description="Reinstate selected members")
    def reinstate_members(self, request, queryset):
        n = 0
        for m in queryset.filter(suspended_at__isnull=False):
            m.suspended_at = None
            m.save(update_fields=["suspended_at", "updated_at"])
            audit(request, "reinstate", m)
            n += 1
        self.message_user(request, f"Reinstated {n} member(s)")

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if change and "organisation" in form.changed_data:
            obj.visible_to_org = False  # the member agreed to be visible to the old organisation, not the new one
        super().save_model(request, obj, form, change)


admin.site.register([Connection, ConnectionRequest, Consent], ReadOnlyAdmin)
