"""Base admin classes. Every change made through the admin is written to AuditLog."""

from django.contrib import admin


def audit(request, action: str, obj, payload: dict | None = None) -> None:
    from apps.moderation.models import AuditLog

    AuditLog.objects.create(
        actor=request.user,
        action=action,
        target_type=obj._meta.label_lower,
        target_id=str(obj.pk),
        payload=payload or {},
    )


class AuditedAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request, "update" if change else "create", obj, {"fields": sorted(form.changed_data)})

    def delete_model(self, request, obj):
        audit(request, "delete", obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            audit(request, "delete", obj)
        super().delete_queryset(request, queryset)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Viewing is allowed; nothing can be added, changed or deleted."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
