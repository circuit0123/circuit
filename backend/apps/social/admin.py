from django.contrib import admin, messages

from apps.social.models import DailyDrop, Follow, MediaUpload, Post, PostMedia, Reaction, Reply
from core.adminbase import AuditedAdmin, ReadOnlyAdmin, audit


class TakedownActions(AuditedAdmin):
    """Hide / remove / restore, each one audit-logged. Moderators change only the status, never the text."""

    def _set(self, request, queryset, status: str, action: str):
        n = 0
        for obj in queryset:
            if obj.status != status:
                before, obj.status = obj.status, status
                obj.save(update_fields=["status"])
                audit(request, action, obj, {"from": before, "to": status})
                n += 1
        self.message_user(request, f"{n} updated", messages.SUCCESS)

    @admin.action(description="Hide (can be restored)")
    def hide(self, request, queryset):
        self._set(request, queryset, "hidden", "hide")

    @admin.action(description="Remove")
    def remove(self, request, queryset):
        self._set(request, queryset, "removed", "remove")

    @admin.action(description="Restore")
    def restore(self, request, queryset):
        self._set(request, queryset, "visible", "restore")


@admin.register(Post)
class PostAdmin(TakedownActions):
    list_display = ("id", "author", "visibility", "status", "created_at")
    list_filter = ("status", "visibility")
    search_fields = ("body",)
    readonly_fields = ("author", "body", "link", "visibility", "capabilities", "created_at")
    actions = ("hide", "remove", "restore")

    def has_add_permission(self, request):
        return False


@admin.register(Reply)
class ReplyAdmin(TakedownActions):
    list_display = ("id", "post", "author", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("post", "author", "body", "parent", "created_at")
    actions = ("hide", "remove", "restore")

    def has_add_permission(self, request):
        return False


admin.site.register([Follow, Reaction, DailyDrop, MediaUpload, PostMedia], ReadOnlyAdmin)
