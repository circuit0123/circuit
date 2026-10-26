from datetime import datetime
from typing import Literal

from ninja import Field, Query, Router, Schema, Status

from apps.accounts.models import Member
from apps.intros import services
from apps.intros.models import IntroRequest
from apps.social import media
from core.auth import current_member
from core.errors import Forbidden
from core.pagination import Page, PageParams, paginate
from core.permissions import NETWORK_ROLES
from core.schemas import PersonOut, person

router = Router()


class PathOut(Schema):
    target: PersonOut
    via: PersonOut | None  # the mutual connection who would vouch for you; None if you are already connected


class IntroIn(Schema):
    target_id: int
    message: str = Field("", max_length=500)


class AnswerIn(Schema):
    accept: bool


class RatingIn(Schema):
    rating: int = Field(ge=1, le=5)


class CapacityOut(Schema):
    allowed: bool  # false for under-18 members and roles that cannot ask for intros
    weekly_limit: int
    used: int
    left: int
    next_frees_at: datetime | None  # when the next one frees up; set only when none are left


class IntroOut(Schema):
    id: int
    my_role: Literal["requester", "broker", "target"]
    status: str  # pending, accepted, declined, expired, completed
    stage: str  # broker, target, done, stopped: who has to answer next
    can_respond: bool
    requester: PersonOut
    target: PersonOut
    via: PersonOut | None
    message: str
    outcome_rating: int | None
    created_at: datetime
    expires_at: datetime


class IntroParams(PageParams):
    box: Literal["sent", "received", "brokered"] = "sent"


def _out(i: IntroRequest, me: Member) -> dict:
    media.prime_photos([i.requester, i.target, *([i.via] if i.via else [])])
    return {
        "id": i.pk, "my_role": "requester" if i.requester_id == me.pk else "broker" if i.via_id == me.pk else "target",
        "status": services.effective_status(i), "stage": i.stage, "can_respond": services.can_respond(i, me),
        "requester": person(i.requester), "target": person(i.target), "via": person(i.via) if i.via else None,
        "message": i.message, "outcome_rating": i.outcome_rating, "created_at": i.created_at, "expires_at": i.expires_at,
    }  # fmt: skip


def _fresh(i: IntroRequest) -> IntroRequest:
    return IntroRequest.objects.select_related("requester", "target", "via").get(pk=i.pk)


def _check_role(member: Member) -> None:
    if member.role not in NETWORK_ROLES:
        raise Forbidden()


@router.get(
    "/capacity",
    response=CapacityOut,
    summary="Introductions left this week",
    description="How many of this week's introductions I have used and left, and when the next one frees up, so the request sheet "
    "can say '2 left' before I press Send. Only about me; how full another person is stays private.",
)
def capacity(request):
    return services.capacity(current_member(request))


@router.get(
    "/path/{target_id}",
    response=PathOut,
    summary="Preview a warm path",
    description="Who would introduce me to this person: the best mutual connection within two hops. "
    "404 if the person is hidden or I have no mutual connection.",
)
def preview_path(request, target_id: int):
    target, broker = services.warm_path(current_member(request), target_id)
    return {"target": person(target), "via": person(broker) if broker else None}


@router.post(
    "",
    response={200: IntroOut, 201: IntroOut},
    summary="Ask for a warm intro",
    description="Ask for an introduction to someone through my best mutual connection, who is asked first and then "
    "the person. 201 for a new request, 200 if one is already open (safe to repeat). At most 3 new requests a week; "
    "409 if the person is not taking more introductions this week. Not available for under-18 accounts. Rate limited.",
)
def request_intro(request, body: IntroIn):
    member = current_member(request)
    intro, created = services.request_intro(member, body.target_id, body.message)
    return Status(201 if created else 200, _out(_fresh(intro), member))


@router.get(
    "",
    response=Page[IntroOut],
    summary="My introductions",
    description="box=sent (what I asked for), received (requests that reached me), brokered (where I am the mutual "
    "connection). Newest first. can_respond says whether it is my turn to answer.",
)
def list_intros(request, params: IntroParams = Query(...)):
    member = current_member(request)
    _check_role(member)
    return paginate(services.inbox(member, params.box), params, lambda i: _out(i, member))


@router.post(
    "/{intro_id}/respond",
    response=IntroOut,
    summary="Accept or decline",
    description="The mutual connection answers first (accepting means vouching), then the person. "
    "Answering again is safe. Not my turn is a 409; a request I am not part of is a 404.",
)
def respond(request, intro_id: int, body: AnswerIn):
    member = current_member(request)
    return _out(_fresh(services.respond(member, intro_id, body.accept)), member)


@router.post(
    "/{intro_id}/rating",
    response=IntroOut,
    summary="Rate an introduction",
    description="The person who asked rates how it went, 1 to 5. Only after it was accepted. Safe to repeat.",
)
def rate(request, intro_id: int, body: RatingIn):
    member = current_member(request)
    _check_role(member)
    return _out(_fresh(services.rate(member, intro_id, body.rating)), member)
