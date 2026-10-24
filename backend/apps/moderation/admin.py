from django.contrib import admin, messages

from apps.messaging.models import Message
from apps.moderation import actions
from apps.moderation.models import AuditLog, Block, Report
from apps.social.models import Post, Reply
from apps.startups.models import Startup
from core.adminbase import AuditedAdmin, ReadOnlyAdmin, audit


@admin.register(Report)
class ReportAdmin(AuditedAdmin):
    """Moderators work reports here; the report itself stays read-only except its status.

    A reported message is shown here and nowhere else: this is the only way a moderator ever reads a direct message.
    """

    list_display = ("id", "target_type", "target_id", "status", "action", "created_at")
    list_filter = ("status", "target_type")
    readonly_fields = (
        "reporter", "target_type", "target_id", "target_preview", "reason", "handled_by", "action", "handled_at", "created_at",
    )  # fmt: skip
    actions = ("hide", "remove", "warn", "suspend", "dismiss")

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
        if obj.target_type == "startup":
            st = Startup.objects.filter(pk=obj.target_id).first()
            return (
                f"{'[hidden] ' if st and st.hidden_at else ''}{st.name} ({st.website_domain}): {st.description}"
                if st
                else "(deleted)"
            )
        return f"member {obj.target_id}: hide the profile, warn or suspend here, or verify on the Member page"

    def _act(self, request, queryset, action: str) -> None:
        changed = 0
        for r in queryset:
            result = actions.apply(r, action, request.user)
            changed += result["changed"]
            audit(request, action, r, result)
        self.message_user(request, f"{queryset.count()} reports: {action} ({changed} changed something)", messages.SUCCESS)

    @admin.action(description="Hide the reported content or profile and mark as actioned")
    def hide(self, request, queryset):
        self._act(request, queryset, "hide")

    @admin.action(description="Remove the reported content and mark as actioned")
    def remove(self, request, queryset):
        self._act(request, queryset, "remove")

    @admin.action(description="Warn the author (in the app and by email) and mark as actioned")
    def warn(self, request, queryset):
        self._act(request, queryset, "warn")

    @admin.action(description="Suspend the author (or the startup's claimant) and mark as actioned")
    def suspend(self, request, queryset):
        self._act(request, queryset, "suspend")

    @admin.action(description="Dismiss (no action needed)")
    def dismiss(self, request, queryset):
        self._act(request, queryset, "dismiss")

    def save_model(self, request, obj, form, change):
        obj.handled_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register([Block, AuditLog], ReadOnlyAdmin)
