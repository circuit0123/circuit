from django.contrib import admin

from apps.organisations.models import Organisation
from core.adminbase import AuditedAdmin


@admin.register(Organisation)
class OrganisationAdmin(AuditedAdmin):
    list_display = ("id", "name", "kind", "city", "join_code")
    search_fields = ("name",)
