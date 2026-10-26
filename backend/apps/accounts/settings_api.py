"""Settings screen endpoints (DESIGN.md §4 "Settings"): one read for the whole screen, one small write per section."""

from datetime import datetime
from typing import Literal

from django.conf import settings
from ninja import Router, Schema
from pydantic import ConfigDict, StrictBool

from apps.accounts import appearance, consent, services
from apps.accounts.api import AppearanceOut
from apps.accounts.models import DataExport, Member
from apps.moderation.models import Block
from apps.notifications import prefs
from core import gate
from core.auth import current_member
from core.ratelimit import check_rate

router = Router()


# -- schemas ---------------------------------------------------------------------------------------
class ChannelsOut(Schema):
    in_app: bool
    email: bool
    push: bool  # stored only: nothing sends a push until F7


class QuietHours(Schema):
    start: int  # IST hour, 0-23: quiet from here ...
    end: int  # ... until here


class NotificationPrefsOut(Schema):
    intros: ChannelsOut
    applications: ChannelsOut
    circuits: ChannelsOut
    messages: ChannelsOut
    pulse_replies: ChannelsOut
    announcements: ChannelsOut
    quiet_hours: QuietHours
    push_daily_cap: int
    quiet_hours_locked: bool  # true for under-18 members: the window is fixed


class ChannelsPatch(Schema):
    model_config = ConfigDict(extra="forbid")
    in_app: StrictBool | None = None
    email: StrictBool | None = None
    push: StrictBool | None = None


class NotificationPrefsPatch(Schema):
    model_config = ConfigDict(extra="forbid")
    intros: ChannelsPatch | None = None
    applications: ChannelsPatch | None = None
    circuits: ChannelsPatch | None = None
    messages: ChannelsPatch | None = None
    pulse_replies: ChannelsPatch | None = None
    announcements: ChannelsPatch | None = None
    quiet_hours: QuietHours | None = None
    push_daily_cap: int | None = None


class PrivacyOut(Schema):
    profile_visibility: Literal["public", "members", "hidden"]
    visible_to_org: bool
    circuits_opt_in: bool
    allow_requests: bool  # strangers may send message and connection requests (always false for under-18s)
    read_receipts: bool  # show read ticks on my messages; the other person sees them only when they have it on too


class PrivacyPatch(Schema):
    model_config = ConfigDict(extra="forbid")
    profile_visibility: Literal["public", "members", "hidden"] | None = None
    visible_to_org: StrictBool | None = None
    circuits_opt_in: StrictBool | None = None
    allow_requests: StrictBool | None = None
    read_receipts: StrictBool | None = None


class AppearancePatch(Schema):
    model_config = ConfigDict(extra="forbid")
    theme: Literal["system", "dark", "light"] | None = None
    accent: Literal["emerald", "mint", "sky", "indigo", "rose", "lime", "mono"] | None = None  # "mint" is the old name of emerald
    swipe_tabs: StrictBool | None = None


class ProfileSummary(Schema):
    display_name: str
    role: str
    city: str
    college: str
    is_minor: bool
    verification_level: int
    email_hint: str  # "a***@gmail.com": enough to recognise it, never the address


class ExportStatus(Schema):
    status: str
    requested_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None


class ConsentStatus(Schema):
    policy_version: str  # the current version
    accepted_version: str | None
    accepted_at: datetime | None
    needs_consent: bool


class GrievanceOut(Schema):
    name: str
    email: str
    address: str


class SupportOut(Schema):
    support_email: str
    grievance: GrievanceOut


class SettingsOut(Schema):
    profile: ProfileSummary
    privacy: PrivacyOut
    appearance: AppearanceOut
    notifications: NotificationPrefsOut
    blocked_count: int
    export: ExportStatus | None
    consent: ConsentStatus
    support: SupportOut


class ConsentIn(Schema):
    policy_version: str


class ConsentOut(Schema):
    policy_version: str
    accepted_at: datetime


# -- helpers ---------------------------------------------------------------------------------------
def email_hint(email: str) -> str:
    local, _, domain = email.partition("@")
    if not local or not domain:
        return ""
    return f"{local[0]}***@{domain}"


def support_info() -> dict:
    return {"support_email": settings.SUPPORT_EMAIL, "grievance": settings.GRIEVANCE}


def _privacy(m: Member) -> dict:
    return {
        "profile_visibility": m.profile_visibility, "visible_to_org": m.visible_to_org,
        "circuits_opt_in": m.circuits_opt_in, "allow_requests": m.allow_requests,
        "read_receipts": m.read_receipts,
    }  # fmt: skip


def settings_for(m: Member) -> dict:
    last_export = DataExport.objects.filter(member=m).order_by("-requested_at", "-id").first()
    accepted = consent.latest(m)
    return {
        "profile": {
            "display_name": m.display_name, "role": m.role, "city": m.city, "college": m.college, "is_minor": m.is_minor,
            "verification_level": m.verification_level, "email_hint": email_hint(m.email),
        },
        "privacy": _privacy(m),
        "appearance": appearance.resolved(m),
        "notifications": prefs.full(m),
        "blocked_count": Block.objects.filter(blocker=m).count(),
        "export": last_export,
        "consent": {
            "policy_version": settings.POLICY_VERSION,
            "accepted_version": accepted.policy_version if accepted else None,
            "accepted_at": accepted.accepted_at if accepted else None,
            "needs_consent": gate.needs_consent(m),
        },
        "support": support_info(),
    }  # fmt: skip


# -- endpoints -------------------------------------------------------------------------------------
@router.get(
    "/me/settings",
    response=SettingsOut,
    summary="Settings screen",
    description="Everything the Settings screens show, in one call: profile summary (email as a hint only), privacy, appearance, "
    "notification preferences per type and channel, how many people I have blocked, my latest data export, which policy "
    "version I accepted, and the support and grievance contacts.",
)
def get_settings(request):
    return settings_for(current_member(request))


@router.patch(
    "/me/privacy",
    response=PrivacyOut,
    summary="Update my privacy",
    description="Send only the fields to change: profile_visibility (public, members, hidden), visible_to_org, circuits_opt_in "
    "(needs verification level 2) and allow_requests (strangers may send requests). Members under 18 can never make the profile "
    "public or open requests to strangers: 403 `under_18_restricted`, whatever the client sends. Unknown fields are a 422.",
)
def patch_privacy(request, body: PrivacyPatch):
    member = current_member(request)
    check_rate(member.pk, "settings_write")
    return _privacy(services.update_privacy(member, body.dict(exclude_unset=True)))


@router.patch(
    "/me/appearance",
    response=AppearanceOut,
    summary="Update my appearance",
    description="Theme (system, dark, light), personal accent (emerald, sky, indigo, rose, lime, mono; the old name 'mint' is still accepted and stored as emerald) and swipe between tabs. "
    "Send only the fields to change. Any other value or field is a 422. Stored on the member so it follows them across devices.",
)
def patch_appearance(request, body: AppearancePatch):
    member = current_member(request)
    check_rate(member.pk, "settings_write")
    return appearance.update(member, body.dict(exclude_unset=True))


@router.patch(
    "/me/notification-preferences",
    response=NotificationPrefsOut,
    summary="Update my notification preferences",
    description="Per type (intros, applications, circuits, messages, pulse_replies, announcements) and channel (in_app, email, push), "
    "plus quiet_hours {start, end} (IST hours, default 22 to 8) and push_daily_cap (1 to 10, default 3). Push is stored only: nothing "
    "sends a push yet. Members under 18 cannot change quiet hours or raise the cap above 3 (403 `under_18_restricted`). "
    'Send only what changes, e.g. {"intros": {"email": false}}. Account notices (a warning from a moderator) are always shown '
    "in the app and cannot be turned off.",
)
def patch_notification_preferences(request, body: NotificationPrefsPatch):
    member = current_member(request)
    check_rate(member.pk, "settings_write")
    return prefs.update(member, body.dict(exclude_unset=True))


@router.post(
    "/me/consent",
    response=ConsentOut,
    summary="Accept the current policy",
    description="Records that I accepted the current Privacy Policy and Terms (policy_version from `/api/me`). Safe to repeat. "
    "A version that is not the current one is a 422. Open to members who have not accepted yet and to members without beta access.",
)
def accept_consent(request, body: ConsentIn):
    member = current_member(request)
    check_rate(member.pk, "consent")
    return consent.accept(member, body.policy_version)
