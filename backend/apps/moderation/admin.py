from django.contrib import admin

from apps.moderation.models import AuditLog, Block, Report
from core.adminbase import AuditedAdmin, ReadOnlyAdmin


@admin.register(Report)
class ReportAdmin(AuditedAdmin):
    """Moderators work reports here; the report itself stays read-only except its status."""

    list_display = ("id", "target_type", "target_id", "status", "created_at")
    list_filter = ("status", "target_type")
    readonly_fields = ("reporter", "target_type", "target_id", "reason", "handled_by", "created_at")

    def save_model(self, request, obj, form, change):
        obj.handled_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register([Block, AuditLog], ReadOnlyAdmin)
