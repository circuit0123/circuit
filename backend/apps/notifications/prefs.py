"""Notification preferences: per type (intros, applications, ...) and channel (in-app, email, push). Stored on the member.

Missing keys mean the defaults, so adding a type later needs no data migration. Account notices (a warning from a moderator,
a startup you claimed) are not a type: they are always in-app, never email, and cannot be turned off, because they carry
safety or account information.

Push is a stored setting only: nothing sends a push yet (F7). Quiet hours and the daily cap live under the `delivery` key beside
the types. Under-18 members have a fixed window (settings.QUIET_HOURS_IST is when they may be reached) that they cannot change.
"""

from django.conf import settings

from apps.accounts.models import Member
from apps.events.services import record
from core.errors import ApiError

TYPES = ("intros", "applications", "circuits", "messages", "pulse_replies", "announcements")
CHANNELS = ("in_app", "email", "push")
EMAIL_BY_DEFAULT = {"intros", "applications", "circuits"}  # the rest are in-app only until the member opts in to email
PUSH_BY_DEFAULT = set(TYPES) - {"announcements"}
DEFAULT_QUIET = (22, 8)  # IST hours, DESIGN.md §8
DEFAULT_PUSH_CAP = 3
MAX_PUSH_CAP = 10

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
    return {t: {"in_app": True, "email": t in EMAIL_BY_DEFAULT, "push": t in PUSH_BY_DEFAULT} for t in TYPES}


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


def delivery(member: Member) -> dict:
    """Quiet hours and the daily push cap. For under-18s the window is fixed: they may be reached only inside QUIET_HOURS_IST."""
    stored = member.notification_prefs.get("delivery") if isinstance(member.notification_prefs, dict) else None
    stored = stored if isinstance(stored, dict) else {}
    start, end = DEFAULT_QUIET
    if isinstance(stored.get("quiet_start"), int) and isinstance(stored.get("quiet_end"), int):
        start, end = stored["quiet_start"], stored["quiet_end"]
    cap = stored.get("push_daily_cap")
    cap = cap if isinstance(cap, int) and 1 <= cap <= MAX_PUSH_CAP else DEFAULT_PUSH_CAP
    if member.is_minor:
        start, end = settings.QUIET_HOURS_IST[1], settings.QUIET_HOURS_IST[0]  # quiet from 19:00 to 09:00
        cap = min(cap, DEFAULT_PUSH_CAP)
    return {"quiet_hours": {"start": start, "end": end}, "push_daily_cap": cap, "quiet_hours_locked": member.is_minor}


def full(member: Member) -> dict:
    """What the Settings screen and the preferences endpoint show: every type, then the delivery settings."""
    return {**resolved(member), **delivery(member)}


def wants(member: Member, kind: str, channel: str) -> bool:
    """Does this member want this kind of notification on this channel? Account notices: in-app yes, email no."""
    type_ = type_for(kind)
    if type_ is None:
        return channel == "in_app"
    return resolved(member)[type_][channel]


def update(member: Member, changes: dict) -> dict:
    """Merge a partial change like {"intros": {"email": False}, "push_daily_cap": 2}. Unknown types or channels raise 422.
    An under-18 member cannot change quiet hours or raise the push cap above the default (403)."""
    current = resolved(member)
    changes = dict(changes)
    quiet = changes.pop("quiet_hours", None)
    cap = changes.pop("push_daily_cap", None)
    for type_, channels in changes.items():
        if type_ not in TYPES or not isinstance(channels, dict):
            raise ApiError(422, "validation_error", f"Unknown notification type: {type_}")
        for channel, value in channels.items():
            if channel not in CHANNELS or not isinstance(value, bool):
                raise ApiError(422, "validation_error", f"Invalid notification setting: {type_}.{channel}")
            current[type_][channel] = value
    stored = member.notification_prefs.get("delivery") if isinstance(member.notification_prefs, dict) else None
    stored = dict(stored) if isinstance(stored, dict) else {}
    if quiet is not None:
        if member.is_minor:
            raise ApiError(403, "under_18_restricted", "Quiet hours are fixed for members under 18.")
        start, end = quiet.get("start"), quiet.get("end")
        if not all(isinstance(h, int) and not isinstance(h, bool) and 0 <= h <= 23 for h in (start, end)) or start == end:
            raise ApiError(422, "validation_error", "Quiet hours need two different hours between 0 and 23.")
        stored["quiet_start"], stored["quiet_end"] = start, end
    if cap is not None:
        if not isinstance(cap, int) or isinstance(cap, bool) or not 1 <= cap <= MAX_PUSH_CAP:
            raise ApiError(422, "validation_error", f"The daily push cap is between 1 and {MAX_PUSH_CAP}.")
        if member.is_minor and cap > DEFAULT_PUSH_CAP:
            raise ApiError(403, "under_18_restricted", f"Members under 18 get at most {DEFAULT_PUSH_CAP} pushes a day.")
        stored["push_daily_cap"] = cap
    member.notification_prefs = {**current, "delivery": stored} if stored else current
    member.save(update_fields=["notification_prefs", "updated_at"])
    record("member.notification_prefs_updated", actor=member, target_type="member", target_id=member.pk, types=sorted(changes))
    return full(member)


def turn_off_email(member: Member, type_: str) -> None:
    """Used by the unsubscribe link: only this type's email channel changes. Idempotent."""
    if type_ not in TYPES:
        raise ApiError(422, "validation_error", "Unknown notification type")
    if resolved(member)[type_]["email"]:
        update(member, {type_: {"email": False}})
