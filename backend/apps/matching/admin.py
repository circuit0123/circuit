from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join

from apps.matching.models import (
    Capability,
    FeatureSnapshot,
    MatchResult,
    MemberSkill,
    MemberTrait,
    ModelVersion,
    Need,
    Offer,
    Trait,
)
from apps.matching.ranker import registry
from apps.matching.ranker.report import arm_report
from core.adminbase import AuditedAdmin, ReadOnlyAdmin

admin.site.register([Capability, Trait], AuditedAdmin)
admin.site.register([MemberSkill, MemberTrait, Need, Offer, MatchResult, FeatureSnapshot], ReadOnlyAdmin)


@admin.register(ModelVersion)
class ModelVersionAdmin(ReadOnlyAdmin):
    """Learned rankers. The only way to change one is a promotion action, which goes through `registry.promote`: it enforces
    the order, the quality gate and the production guard, and writes the audit row. A refusal is shown and nothing changes."""

    list_display = ("version", "status", "data_source", "trained_env", "beats_rule", "fairness_passed", "trained_at")
    list_filter = ("status", "data_source", "trained_env")
    ordering = ("-trained_at",)
    readonly_fields = ("ab_report",)
    actions = ("to_shadow", "to_ab", "to_active", "retire")

    @admin.display(description="Seen by members (last 28 days)")
    def ab_report(self, obj):
        rows = [r for r in arm_report(28) if r["model_version"] == obj.version]
        if not rows:
            return "Nothing shown yet."
        return format_html_join(
            "", "<div>{} arm: shown {}, asked for an intro {} ({:.1%}), accepted {} ({:.1%})</div>",
            ((r["arm"], r["shown"], r["requested"], r["request_rate"], r["accepted"], r["accept_rate"]) for r in rows),
        )  # fmt: skip

    def _move(self, request, queryset, to: str) -> None:
        for mv in queryset:
            try:
                registry.promote(mv, to, request.user)
            except registry.PromotionRefused as why:
                self.message_user(request, f"Not changed: {why}", messages.ERROR)
            else:
                self.message_user(request, format_html("{} is now {}.", mv.version, to), messages.SUCCESS)

    @admin.action(description="Move to shadow (scores are logged; members still see the rule)")
    def to_shadow(self, request, queryset):
        self._move(request, queryset, "shadow")

    @admin.action(description="Move to A/B (the model orders the lists of a share of members)")
    def to_ab(self, request, queryset):
        self._move(request, queryset, "ab")

    @admin.action(description="Make active (the model orders everyone's list)")
    def to_active(self, request, queryset):
        self._move(request, queryset, "active")

    @admin.action(description="Retire")
    def retire(self, request, queryset):
        self._move(request, queryset, "retired")
