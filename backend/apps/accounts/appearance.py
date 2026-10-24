"""Appearance settings stored on the member so they follow across devices (DESIGN.md §5 "Personal accent").

Only these values exist. The API schema rejects anything else with a 422, and `update` checks again so a caller that skips
the schema (a job, the admin) cannot store a colour that was never contrast-checked.
"""

from apps.accounts.models import Member
from apps.events.services import record
from core.errors import ApiError

THEMES = ("system", "dark", "light")
ACCENTS = ("mint", "sky", "indigo", "rose", "lime", "mono")
DEFAULTS = {"theme": "system", "accent": "mint", "swipe_tabs": True}


def resolved(member: Member) -> dict:
    """The member's settings with defaults filled in. Unknown or invalid stored values fall back to the default."""
    stored = member.appearance if isinstance(member.appearance, dict) else {}
    theme = stored.get("theme")
    accent = stored.get("accent")
    swipe = stored.get("swipe_tabs")
    return {
        "theme": theme if theme in THEMES else DEFAULTS["theme"],
        "accent": accent if accent in ACCENTS else DEFAULTS["accent"],
        "swipe_tabs": swipe if isinstance(swipe, bool) else DEFAULTS["swipe_tabs"],
    }


def update(member: Member, changes: dict) -> dict:
    """Apply a partial change (only the keys the client sent). Raises 422 for an unknown key or value."""
    for key, value in changes.items():
        if key == "theme" and value in THEMES:
            continue
        if key == "accent" and value in ACCENTS:
            continue
        if key == "swipe_tabs" and isinstance(value, bool):
            continue
        raise ApiError(422, "validation_error", f"Invalid appearance setting: {key}")
    member.appearance = {**resolved(member), **changes}
    member.save(update_fields=["appearance", "updated_at"])
    record("member.appearance_updated", actor=member, target_type="member", target_id=member.pk, fields=sorted(changes))
    return member.appearance
