"""Public unsubscribe endpoints: work without signing in, because the signed token in the link is the proof (RFC 8058 one-click)."""

from ninja import Router, Schema

from apps.accounts.models import Member
from apps.events.services import record
from apps.notifications import copy, prefs, unsubscribe
from core.errors import ApiError
from core.ratelimit import check_rate, ip_key

router = Router()


class UnsubscribeOut(Schema):
    type: str  # the notification type, e.g. "intros"
    label: str  # how to say it in a sentence: "introductions"
    email_on: bool  # is email still switched on for this type?


def _invalid() -> ApiError:
    return ApiError(400, "invalid_token", "This link is not valid or has expired. You can change email settings in the app.")


def _member_and_type(request, token: str) -> tuple[Member, str]:
    check_rate(ip_key(request), "unsubscribe_ip")
    parsed = unsubscribe.read_token(token)
    if parsed is None:
        raise _invalid()
    member = Member.objects.filter(pk=parsed[0], deleted_at__isnull=True, deletion_requested_at__isnull=True).first()
    if member is None:
        raise _invalid()
    return member, parsed[1]


def _out(member: Member, type_: str) -> dict:
    return {"type": type_, "label": copy.TYPE_LABELS[type_], "email_on": prefs.resolved(member)[type_]["email"]}


@router.get(
    "/unsubscribe",
    auth=None,
    response=UnsubscribeOut,
    summary="Check an unsubscribe link",
    description="Public. Shows which email type the link switches off. Changes nothing, so mail scanners that open links are "
    "harmless. A tampered or expired token is a 400 `invalid_token`. Rate limited per address.",
)
def check_unsubscribe(request, token: str):
    member, type_ = _member_and_type(request, token)
    return _out(member, type_)


@router.post(
    "/unsubscribe",
    auth=None,
    response=UnsubscribeOut,
    summary="Unsubscribe from one type of email",
    description="Public, one click (also the target of the List-Unsubscribe-Post header). Turns off the email channel of the "
    "one notification type in the link and nothing else. Safe to repeat. A tampered or expired token is a 400 `invalid_token`.",
)
def do_unsubscribe(request, token: str):
    member, type_ = _member_and_type(request, token)
    if prefs.resolved(member)[type_]["email"]:
        prefs.turn_off_email(member, type_)
        record("email.unsubscribed", actor=member, target_type="member", target_id=member.pk, notification_type=type_)
    return _out(member, type_)
