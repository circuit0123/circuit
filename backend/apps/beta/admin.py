"""Super admins run the beta here: codes, waitlist, allowlist, access. Every action is written to the audit log with ids only."""

from django import forms
from django.contrib import admin
from django.utils import timezone

from apps.beta import services
from apps.beta.models import AllowlistEntry, BetaAccess, InviteCode, WaitlistEntry
from core.adminbase import AuditedAdmin, audit
from core.codes import plain_email


class RedemptionInline(admin.TabularInline):
    model = BetaAccess
    fk_name = "invite_code"
    fields = ("member", "granted_at", "revoked_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name_plural = "Used by"

    def has_add_permission(self, request, obj=None):
        return False


class InviteCodeForm(forms.ModelForm):
    class Meta:
        model = InviteCode
        fields = ["max_uses", "expires_at", "organisation", "note"]

    def clean_max_uses(self):
        value = self.cleaned_data["max_uses"]
        if value < 1:
            raise forms.ValidationError("At least 1")
        if self.instance.pk and value < self.instance.uses:
            raise forms.ValidationError(f"Already used {self.instance.uses} times")
        return value


@admin.register(InviteCode)
class InviteCodeAdmin(AuditedAdmin):
    """Create a code (it is generated, never typed), see who used it, revoke it. Codes are never deleted: revoke instead."""

    form = InviteCodeForm
    list_display = ("code", "kind", "usage", "state", "expires_at", "organisation", "created_by", "created_at")
    list_filter = ("kind", "organisation")
    search_fields = ("code", "note")
    readonly_fields = ("code", "kind", "uses", "created_by", "created_by_staff", "revoked_at", "created_at")
    fields = (
        "code",
        "kind",
        "max_uses",
        "uses",
        "expires_at",
        "organisation",
        "note",
        "created_by",
        "created_by_staff",
        "revoked_at",
        "created_at",
    )
    inlines = [RedemptionInline]
    actions = ["revoke_codes"]

    @admin.display(description="Uses")
    def usage(self, obj):
        return f"{obj.uses}/{obj.max_uses}"

    @admin.display(description="State")
    def state(self, obj):
        return services.code_status(obj)

    @admin.action(description="Revoke selected codes (people who already got in stay in)")
    def revoke_codes(self, request, queryset):
        n = 0
        for code in queryset:
            if services.revoke_code(code):
                audit(request, "invite.revoke", code)
                n += 1
        self.message_user(request, f"Revoked {n} code(s)")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.code = services.generate_code()
            obj.kind = InviteCode.Kind.ADMIN
            obj.created_by_staff = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(AuditedAdmin):
    """Approve (access + invite email) or reject. The entry itself is read-only."""

    list_display = ("id", "email", "role", "city", "college", "status", "src", "created_at")
    list_filter = ("status", "role", "city", "src")
    search_fields = ("email", "college")
    readonly_fields = [f.name for f in WaitlistEntry._meta.fields]
    actions = ["approve_entries", "reject_entries"]

    @admin.action(description="Approve and send the invite email")
    def approve_entries(self, request, queryset):
        n = sum(1 for entry in queryset if services.approve_waitlist(entry, request.user) is not None)
        self.message_user(request, f"Approved {n} entr{'y' if n == 1 else 'ies'} and queued the invite email")

    @admin.action(description="Reject (no email is sent)")
    def reject_entries(self, request, queryset):
        n = sum(
            1 for entry in queryset.exclude(status=WaitlistEntry.Status.APPROVED) if services.reject_waitlist(entry, request.user)
        )
        self.message_user(
            request, f"Rejected {n} entr{'y' if n == 1 else 'ies'}. Approved entries are left alone: revoke their access instead"
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # view only; approve and reject are actions, so each one is audited


class AllowlistForm(forms.ModelForm):
    class Meta:
        model = AllowlistEntry
        fields = ["email", "note"]

    def clean_email(self):
        email = plain_email(self.cleaned_data["email"].strip())
        if email is None:
            raise forms.ValidationError("Enter a plain address like name@example.com (ASCII only)")
        if AllowlistEntry.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Already on the allowlist")
        return email


@admin.register(AllowlistEntry)
class AllowlistEntryAdmin(AuditedAdmin):
    """Emails that get in without a code. Matched only against the address the sign-in provider verified."""

    form = AllowlistForm
    list_display = ("email", "note", "added_by", "created_at")
    search_fields = ("email", "note")
    readonly_fields = ("added_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BetaAccess)
class BetaAccessAdmin(AuditedAdmin):
    """Who is in. Grant a member by hand (add), or revoke and restore with the actions."""

    list_display = ("id", "member", "source", "granted_at", "revoked_at")
    list_filter = ("source", "revoked_at")
    raw_id_fields = ("member",)
    actions = ["revoke_access", "restore_access"]
    _always_readonly = ("source", "invite_code", "granted_at", "revoked_at", "revoked_by")

    def get_fields(self, request, obj=None):
        return ("member",) if obj is None else ("member", *self._always_readonly)

    def get_readonly_fields(self, request, obj=None):
        return self._always_readonly if obj is None else ("member", *self._always_readonly)

    @admin.action(description="Revoke access (locked out of the app at once)")
    def revoke_access(self, request, queryset):
        n = 0
        for access in queryset.select_related("member"):
            if services.revoke_access(access.member, request.user):
                audit(request, "beta.revoke", access)
                n += 1
        self.message_user(request, f"Revoked {n} member(s)")

    @admin.action(description="Restore access")
    def restore_access(self, request, queryset):
        n = 0
        for access in queryset.select_related("member"):
            if services.restore_access(access.member):
                audit(request, "beta.restore", access)
                n += 1
        self.message_user(request, f"Restored {n} member(s)")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.source = BetaAccess.Source.APPROVED
            obj.granted_at = timezone.now()
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False  # revoke instead: a deleted row would let the allowlist quietly re-grant
