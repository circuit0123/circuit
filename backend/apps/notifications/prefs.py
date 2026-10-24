"""Notification preferences: per type (intros, applications, ...) and channel (in-app, email). Stored on the member.

Missing keys mean the defaults, so adding a type later needs no data migration. Account notices (a warning from a moderator,
a startup you claimed) are not a type: they are always in-app, never email, and cannot be turned off, because they carry
safety or account information.
"""

from apps.accounts.models import Member
from apps.events.services import record
from core.errors import ApiError

TYPES = ("intros", "applications", "circuits", "messages", "pulse_replies", "announcements")
CHANNELS = ("in_app", "email")
EMAIL_BY_DEFAULT = {"intros", "applications", "circuits"}  # the rest are in-app only until the member opts in to email

# notification kind prefix -> type. A kind that matches nothing here is an account notice.
KIND_TYPES = {
    "intro.": "intros",
    "application.": "applications",
    "circuit.": "circuits",
    "message.": "messages",
    "post.reply": "pulse_replies",
    "announcement.": "announcements",
}


def type_for(kind: str) -> str | None:
    for prefix, type_ in KIND_TYPES.items():
        if kind.startswith(prefix):
            return type_
    return None


def defaults() -> dict[str, dict[str, bool]]:
    return {t: {"in_app": True, "email": t in EMAIL_BY_DEFAULT} for t in TYPES}


def resolved(member: Member) -> dict[str, dict[str, bool]]:
    result = defaults()
    stored = member.notification_prefs if isinstance(member.notification_prefs, dict) else {}
    for type_, channels in result.items():
        row = stored.get(type_)
        if isinstance(row, dict):
            for channel in CHANNELS:
                if isinstance(row.get(channel), bool):
                    channels[channel] = row[channel]
    return result


def wants(member: Member, kind: str, channel: str) -> bool:
    """Does this member want this kind of notification on this channel? Account notices: in-app yes, email no."""
    type_ = type_for(kind)
    if type_ is None:
        return channel == "in_app"
    return resolved(member)[type_][channel]


def update(member: Member, changes: dict[str, dict[str, bool]]) -> dict[str, dict[str, bool]]:
    """Merge a partial change like {"intros": {"email": False}}. Unknown types or channels raise 422."""
    current = resolved(member)
    for type_, channels in changes.items():
        if type_ not in TYPES or not isinstance(channels, dict):
            raise ApiError(422, "validation_error", f"Unknown notification type: {type_}")
        for channel, value in channels.items():
            if channel not in CHANNELS or not isinstance(value, bool):
                raise ApiError(422, "validation_error", f"Invalid notification setting: {type_}.{channel}")
            current[type_][channel] = value
    member.notification_prefs = current
    member.save(update_fields=["notification_prefs", "updated_at"])
    record("member.notification_prefs_updated", actor=member, target_type="member", target_id=member.pk, types=sorted(changes))
    return current


def turn_off_email(member: Member, type_: str) -> None:
    """Used by the unsubscribe link: only this type's email channel changes. Idempotent."""
    if type_ not in TYPES:
        raise ApiError(422, "validation_error", "Unknown notification type")
    if resolved(member)[type_]["email"]:
        update(member, {type_: {"email": False}})
