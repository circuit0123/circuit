from django import forms
from django.contrib import admin

from apps.organisations import services
from apps.organisations.models import Organisation
from core.adminbase import AuditedAdmin, audit


class OrganisationForm(forms.ModelForm):
    email_domains = forms.CharField(
        required=False,
        help_text="Comma-separated, e.g. kit.edu.in. Members who verify an email on one of these join automatically.",
    )

    class Meta:
        model = Organisation
        fields = ["name", "kind", "city", "email_domains"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["email_domains"] = ", ".join(self.instance.email_domains)

    def clean_email_domains(self) -> list[str]:
        raw = [d for d in self.cleaned_data["email_domains"].split(",") if d.strip()]
        try:
            return services.clean_domains(raw, exclude_org_id=self.instance.pk)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc


@admin.register(Organisation)
class OrganisationAdmin(AuditedAdmin):
    """Super admins create organisations here and appoint the first partner admin (on the Member page)."""

    form = OrganisationForm
    list_display = ("id", "name", "kind", "city", "join_code")
    search_fields = ("name",)
    readonly_fields = ("join_code",)
    actions = ["regenerate_join_code"]

    @admin.action(description="Regenerate join code (the old code stops working)")
    def regenerate_join_code(self, request, queryset):
        for org in queryset:
            org.join_code = services.generate_join_code()
            org.save(update_fields=["join_code"])
            audit(request, "regenerate_join_code", org)
        self.message_user(request, f"Regenerated {queryset.count()} join code(s). Members who already joined stay in.")

    def save_model(self, request, obj, form, change):
        if not obj.join_code:
            obj.join_code = services.generate_join_code()
        super().save_model(request, obj, form, change)
