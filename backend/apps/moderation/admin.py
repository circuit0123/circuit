from django.contrib import admin, messages
from django.utils import timezone

from apps.messaging.models import Message
from apps.moderation.models import AuditLog, Block, Report
from apps.social.models import Post, Reply
from core.adminbase import AuditedAdmin, ReadOnlyAdmin, audit


@admin.register(Report)
class ReportAdmin(AuditedAdmin):
    """Moderators work reports here; the report itself stays read-only except its status.

    A reported message is shown here and nowhere else: this is the only way a moderator ever reads a direct message.
    """

    list_display = ("id", "target_type", "target_id", "status", "created_at")
    list_filter = ("status", "target_type")
    readonly_fields = ("reporter", "target_type", "target_id", "target_preview", "reason", "handled_by", "created_at")
    actions = ("take_down", "dismiss")

    @admin.display(description="Reported content")
    def target_preview(self, obj: Report) -> str:
        if obj.target_type == "post":
            p = Post.objects.filter(pk=obj.target_id).first()
            return f"[{p.status}] by member {p.author_id}: {p.body} {p.link}" if p else "(deleted)"
        if obj.target_type == "reply":
            r = Reply.objects.filter(pk=obj.target_id).first()
            return f"[{r.status}] by member {r.author_id}: {r.body}" if r else "(deleted)"
        if obj.target_type == "message":
            m = Message.objects.filter(pk=obj.target_id).first()
            return f"{'[removed] ' if m.removed_at else ''}from member {m.sender_id}: {m.body}" if m else "(deleted)"
        return f"member {obj.target_id}: suspend or verify on the Member page"

    def _take_down(self, report: Report) -> bool:
        if report.target_type in ("post", "reply"):
            model = Post if report.target_type == "post" else Reply
            return bool(model.objects.filter(pk=report.target_id).exclude(status="removed").update(status="removed"))
        if report.target_type == "message":
            return bool(Message.objects.filter(pk=report.target_id, removed_at__isnull=True).update(removed_at=timezone.now()))
        return False

    @admin.action(description="Take down the reported content and mark as actioned")
    def take_down(self, request, queryset):
        for r in queryset:
            done = self._take_down(r)
            r.status, r.handled_by = Report.Status.ACTIONED, request.user
            r.save(update_fields=["status", "handled_by"])
            audit(request, "take_down", r, {"target_type": r.target_type, "target_id": r.target_id, "changed": done})
        self.message_user(request, f"{queryset.count()} reports actioned", messages.SUCCESS)

    @admin.action(description="Dismiss (no action needed)")
    def dismiss(self, request, queryset):
        for r in queryset:
            r.status, r.handled_by = Report.Status.DISMISSED, request.user
            r.save(update_fields=["status", "handled_by"])
            audit(request, "dismiss", r)
        self.message_user(request, f"{queryset.count()} reports dismissed", messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        obj.handled_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register([Block, AuditLog], ReadOnlyAdmin)
