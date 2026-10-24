"""Append-only product events. One function so every action is recorded the same way.

Payloads are pseudonymous: ids and enums only, never names, emails or free text.
Every event type is listed in EVENT_TYPES; recording an unknown one is a bug and raises, so a typo cannot silently
create a new type that nobody counts.
"""

from apps.events.models import Event

EVENT_TYPES = frozenset(
    {
        # accounts and verification
        "member.created", "member.profile_updated", "member.role_changed", "member.needs_set", "member.offers_set",
        "member.skills_set", "member.traits_set", "onboarding.extracted", "verification.work_email_started",
        "verification.level_raised",
        # organisations
        "org.joined", "org.left", "org.member_removed",
        # startups
        "startup.viewed", "startup.interest_added", "startup.interest_removed", "startup.updated", "startup.claim_started",
        "startup.claimed",
        # jobs
        "job.created", "job.updated", "application.created", "application.withdrawn", "application.status_changed",
        # circuits
        "circuit.round_run", "circuit.proposed", "circuit.accepted", "circuit.declined", "circuit.activated",
        "circuit.leg_done", "circuit.rated", "circuit.completed", "circuit.expired",
        # intros
        "intro.requested", "intro.broker_responded", "intro.responded", "intro.rated", "intro.expired",
        # matching
        "matches.computed",
        # notifications
        "notification.read", "notification.read_all",
        # social: build logs, Pulse, Today, Daily Drop, follows, connections (F15-F17)
        "media.uploaded", "post.created", "post.deleted", "reaction.added", "reaction.removed", "reply.created", "reply.deleted",
        "follow.added", "follow.removed", "pulse.seen", "livewire.viewed", "drop.built", "drop.swiped",
        "connection.requested", "connection.responded", "connection.removed",
        # messaging and reports
        "conversation.started", "conversation.accepted", "conversation.blocked", "message.sent", "report.created",
        # invite-only beta (F18)
        "beta.access_granted", "invite.created", "waitlist.joined",
        # account basics and privacy (Stages 6-7)
        "member.privacy_updated", "member.appearance_updated", "member.notification_prefs_updated", "member.blocked",
        "member.unblocked", "consent.accepted", "export.requested", "export.ready", "export.failed", "export.downloaded",
        "account.deletion_requested", "account.deleted", "support.requested", "email.unsubscribed", "report.actioned",
        "retention.cleaned",
        # matching ML (Stage 4c)
        "ranker.trained", "ranker.promoted", "ranker.retired", "onboarding.updated",
    }
)  # fmt: skip


def record(type: str, *, actor=None, target_type: str = "", target_id: int | None = None, **payload) -> Event:
    if type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type {type!r}: add it to EVENT_TYPES")
    return Event.objects.create(
        actor_id=getattr(actor, "pk", actor), type=type, target_type=target_type, target_id=target_id, payload=payload
    )
