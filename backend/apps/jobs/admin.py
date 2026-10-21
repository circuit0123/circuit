from django.contrib import admin

from apps.jobs.models import Application, Job, JobCapability
from core.adminbase import AuditedAdmin, ReadOnlyAdmin


@admin.register(Job)
class JobAdmin(AuditedAdmin):
    list_display = ("id", "title", "startup", "kind", "is_open")
    list_filter = ("kind", "is_open")


admin.site.register([Application, JobCapability], ReadOnlyAdmin)
