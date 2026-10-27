from django import forms
from django.contrib import admin
from django.contrib.gis.geos import Point

from apps.startups.models import ClaimRequest, Startup, StartupInterest, StartupMember, StartupTrait
from core.adminbase import AuditedAdmin, ReadOnlyAdmin


class StartupForm(forms.ModelForm):
    """Edit the pin as two plain numbers (the admin's map widget loads scripts our CSP blocks). Both blank = no pin."""

    latitude = forms.FloatField(required=False, min_value=-90, max_value=90)
    longitude = forms.FloatField(required=False, min_value=-180, max_value=180)

    class Meta:
        model = Startup
        exclude = ("location",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        loc = self.instance.location
        if loc:
            self.initial["latitude"], self.initial["longitude"] = loc.y, loc.x

    def clean(self):
        data = super().clean()
        if (data.get("latitude") is None) != (data.get("longitude") is None):
            raise forms.ValidationError("Fill in both latitude and longitude, or leave both empty for no pin.")
        return data

    def save(self, commit=True):
        lat, lng = self.cleaned_data.get("latitude"), self.cleaned_data.get("longitude")
        self.instance.location = Point(lng, lat, srid=4326) if lat is not None else None
        return super().save(commit)


@admin.register(Startup)
class StartupAdmin(AuditedAdmin):
    """Review crawled startups, fix an address or pin, and handle takedowns (F13)."""

    form = StartupForm
    list_display = ("id", "name", "website_domain", "sector", "hiring", "source", "confidence", "has_pin", "claimed_by")
    list_filter = ("source", "hiring", "sector")
    search_fields = ("name", "website_domain")
    readonly_fields = ("claimed_by", "claimed_at", "view_count")

    @admin.display(boolean=True, description="Pin")
    def has_pin(self, obj) -> bool:
        return obj.location is not None

    def get_fields(self, request, obj=None):
        fields = [f for f in super().get_fields(request, obj) if f not in ("latitude", "longitude")]
        i = fields.index("address") + 1 if "address" in fields else len(fields)
        return [*fields[:i], "latitude", "longitude", *fields[i:]]


admin.site.register([ClaimRequest, StartupInterest, StartupMember, StartupTrait], ReadOnlyAdmin)
