from typing import Literal

from ninja import Router, Schema, Status
from pydantic import Field

from apps.beta import services
from core.auth import current_member
from core.ratelimit import check_rate, ip_key
from core.schemas import SRC_MAX, SRC_PATTERN

router = Router()


class RedeemIn(Schema):
    code: str = Field(max_length=64)  # no min length: an empty code gets the same answer as any other wrong one


class RedeemOut(Schema):
    beta_access: bool
    organisation_id: int | None


@router.post(
    "/beta/redeem",
    response=RedeemOut,
    summary="Use an invite code",
    description="Gives the signed-in member beta access, and joins the code's organisation if it has one and they have none. "
    "A code that is unknown, expired, used up or revoked all get the same 400 `invalid_code` so the answer never helps "
    "guessing. Someone who already has access gets 200 and no code is used. Rate limited per member and per address.",
)
def redeem(request, body: RedeemIn):
    check_rate(ip_key(request), "redeem_ip")
    member = current_member(request)
    check_rate(member.pk, "redeem")
    return services.redeem(member, body.code)


class InviteOut(Schema):
    code: str
    link: str  # APP_URL/join?code=...&src=invite
    status: Literal["available", "used", "expired", "revoked"]


class InvitesOut(Schema):
    items: list[InviteOut]


@router.get(
    "/invites",
    response=InvitesOut,
    summary="My invite codes",
    description="The member's own single-use invite codes with one-tap links to share. Missing codes are created on the way, "
    "up to the beta limit (3 by default), so this is safe to call repeatedly.",
)
def my_invites(request):
    return {"items": services.member_invites(current_member(request))}


class WaitlistIn(Schema):
    email: str = Field(min_length=3, max_length=254)
    role: Literal["student", "founder", "mentor", "investor", "partner"]
    city: str = Field("", max_length=100)
    college: str = Field("", max_length=200)
    note: str = Field("", max_length=500)
    src: str = Field("", max_length=SRC_MAX, pattern=SRC_PATTERN)  # which landing page, e.g. landing-students


class WaitlistOut(Schema):
    status: Literal["ok"]


@router.post(
    "/waitlist",
    auth=None,
    response={202: WaitlistOut},
    summary="Join the waitlist",
    description="Public, for the landing site. No account needed. Always answers 202 `ok` for a valid request, including when the "
    "email is already on the list, so it never reveals who has signed up. Rate limited per address. "
    "The app calls this too, from the invite-code screen.",
)
def join_waitlist(request, body: WaitlistIn):
    check_rate(ip_key(request), "waitlist")
    services.join_waitlist(**body.dict())
    return Status(202, {"status": "ok"})


class VisitIn(Schema):
    src: str = Field("", max_length=SRC_MAX, pattern=SRC_PATTERN)


@router.post(
    "/join/visit",
    auth=None,
    response={204: None},
    summary="Count a landing link opened",
    description="Public. The app's /join page calls it once per browser session with the link's `src`, so the funnel can show "
    "clicks next to sign-ups. Adds 1 to a per-day count for that `src`; nothing about the visitor is stored. "
    "Answers 204. Rate limited per address.",
)
def join_visit(request, body: VisitIn):
    check_rate(ip_key(request), "join_visit")
    services.count_visit(body.src)
    return Status(204, None)
