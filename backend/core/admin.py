from django import forms
from django.contrib import admin, messages

from core import flags
from core.adminbase import ReadOnlyAdmin
from core.models import FeatureFlag, JobRun


class FeatureFlagForm(forms.ModelForm):
    class Meta:
        model = FeatureFlag
        fields = ["audience", "note"]

    def clean(self):
        data = super().clean()
        if self.instance.name and data.get("audience"):
            try:
                flags.check_dependencies({**flags.audiences(), self.instance.name: data["audience"]})
            except ValueError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return data


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """Super admins switch features here. Saves go through flags.set_audience, so they are audit-logged."""

    form = FeatureFlagForm
    list_display = ("name", "audience", "default", "note", "updated_by", "updated_at")
    readonly_fields = ("name", "updated_by", "updated_at")

    @admin.display(description="Default (FEATURES)")
    def default(self, obj):
        return flags.defaults().get(obj.name, "?")

    def changelist_view(self, request, extra_context=None):
        # One row per known flag, so every flag is listed even before anyone overrides it.
        for name, audience in flags.defaults().items():
            FeatureFlag.objects.get_or_create(name=name, defaults={"audience": audience})
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        try:
            flags.set_audience(obj.name, obj.audience, actor=request.user, note=obj.note)
        except ValueError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)


@admin.register(JobRun)
class JobRunAdmin(ReadOnlyAdmin):
    """When each scheduled job last ran and how it ended (ok, skipped, failed). Jobs write this themselves (core/jobs.py)."""

    list_display = ("name", "last_status", "last_success_at", "last_started_at", "last_finished_at", "overdue", "last_error")
    ordering = ("name",)

    @admin.display(boolean=True, description="Overdue")
    def overdue(self, obj):
        from core import jobhealth

        return any(s.overdue for s in jobhealth.status() if s.name == obj.name)
