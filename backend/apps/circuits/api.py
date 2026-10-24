from datetime import datetime

from django.utils import timezone
from ninja import Field, Query, Router, Schema

from apps.circuits import services
from apps.circuits.models import Circuit, CircuitLeg
from core.auth import current_member
from core.errors import Conflict, Forbidden
from core.flags import require_flag
from core.pagination import Page, PageParams, paginate
from core.permissions import NETWORK_ROLES
from core.schemas import PersonOut, person

router = Router()


class LegOut(Schema):
    id: int
    giver: PersonOut
    receiver: PersonOut
    capability: str  # what is being given, e.g. "Brand marketing"
    consent: str  # pending, accepted, declined: the giver's yes or no to the whole loop
    fulfilled: bool  # the giver marked it done
    rated: bool  # the receiver has rated it
    rating: int | None  # 1-5; only on the legs I am part of (the third member's legs show `rated` only)
    i_give: bool
    i_receive: bool
    can_mark_done: bool  # I give this, the circuit is active and it is not done yet
    can_rate: bool  # I receive this, it is done and I have not rated it yet


class MemberStatusOut(Schema):
    person: PersonOut
    is_me: bool
    consent: str  # pending, accepted, declined: lights up this person's segment of the ring
    done: bool  # this person has marked their handover done


class LineOut(Schema):
    person: PersonOut  # the other person
    capability: str


class CircuitOut(Schema):
    id: int
    status: str  # proposed, active, completed, expired, declined
    score_percent: int  # the weakest handover in the loop
    week: str
    consent_deadline: datetime
    time_left_seconds: int | None  # while proposed: seconds to answer; otherwise null
    created_at: datetime
    my_consent: str
    next_step: str  # answer, waiting, mark_done, rate or none: what the screen should offer me now
    you_help: LineOut  # "You help Priya with fundraising"
    helps_you: LineOut  # "Arjun helps you with marketing"
    members: list[MemberStatusOut]  # the three people, in ring order, with consent and done
    legs: list[LegOut]


class AnswerIn(Schema):
    accept: bool


class RatingIn(Schema):
    rating: int = Field(ge=1, le=5)


def _next_step(status: str, mine: CircuitLeg, got: CircuitLeg) -> str:
    unrated = got.fulfilled and got.rating is None
    if status == Circuit.Status.PROPOSED:
        return "answer" if mine.consent == CircuitLeg.Consent.PENDING else "waiting"
    if status == Circuit.Status.ACTIVE:
        if not mine.fulfilled:
            return "mark_done"
        return "rate" if unrated else "waiting"
    if status == Circuit.Status.COMPLETED and unrated:
        return "rate"
    return "none"


def _out(c: Circuit, me) -> dict:
    """Everything the circuit screen and the completion moment show, in one response (DESIGN.md §4 Circuits)."""
    legs = sorted(c.legs.all(), key=lambda leg: leg.pk)
    mine = next(leg for leg in legs if leg.giver_id == me.pk)  # the leg I give carries my consent and my "done"
    got = next(leg for leg in legs if leg.receiver_id == me.pk)
    status = services.effective_status(c)
    now = timezone.now()
    active = status == Circuit.Status.ACTIVE
    return {
        "id": c.pk, "status": status, "score_percent": round(c.score * 100), "week": c.round.week,
        "consent_deadline": c.consent_deadline, "created_at": c.created_at, "my_consent": mine.consent,
        "time_left_seconds": max(0, int((c.consent_deadline - now).total_seconds())) if status == Circuit.Status.PROPOSED else None,
        "next_step": _next_step(status, mine, got),
        "you_help": {"person": person(mine.receiver), "capability": mine.capability.name},
        "helps_you": {"person": person(got.giver), "capability": got.capability.name},
        "members": [
            {"person": person(leg.giver), "is_me": leg.giver_id == me.pk, "consent": leg.consent, "done": leg.fulfilled}
            for leg in legs
        ],
        "legs": [
            {
                "id": leg.pk, "giver": person(leg.giver), "receiver": person(leg.receiver), "capability": leg.capability.name,
                "consent": leg.consent, "fulfilled": leg.fulfilled, "rated": leg.rating is not None,
                "rating": leg.rating if me.pk in (leg.giver_id, leg.receiver_id) else None,
                "i_give": leg.giver_id == me.pk, "i_receive": leg.receiver_id == me.pk,
                "can_mark_done": leg.giver_id == me.pk and active and not leg.fulfilled,
                "can_rate": leg.receiver_id == me.pk and leg.fulfilled and leg.rating is None and status in (Circuit.Status.ACTIVE, Circuit.Status.COMPLETED),
            }
            for leg in legs
        ],
    }  # fmt: skip


def _check_role(member) -> None:
    if member.role not in NETWORK_ROLES:
        raise Forbidden()


@router.get(
    "",
    response=Page[CircuitOut],
    summary="My circuits",
    description="Exchange circuits I am part of, newest first, each with everything its screen shows (see One circuit). "
    "A proposal nobody finished answering in 72 hours reads as expired.",
)
@require_flag("circuits")
def list_circuits(request, params: PageParams = Query(...)):
    member = current_member(request)
    _check_role(member)
    return paginate(services.my_circuits(member), params, lambda c: _out(c, member))


@router.get(
    "/{circuit_id}",
    response=CircuitOut,
    summary="One circuit",
    description="A circuit I am part of; anyone else's is a 404. One call returns everything the circuit screen and the completion "
    "moment need: the three members with their yes and their done, who helps whom (`you_help`, `helps_you`), the time left to "
    "answer, what I can do next (`next_step`), each handover with `can_mark_done` and `can_rate`, and ratings (a rating shows "
    "only on handovers I give or receive). Realtime: listen to the private channel `circuit:<id>`; an event means refetch.",
)
@require_flag("circuits")
def get_circuit(request, circuit_id: int):
    member = current_member(request)
    _check_role(member)
    return _out(services.get_circuit(member, circuit_id), member)


@router.post(
    "/{circuit_id}/respond",
    response=CircuitOut,
    summary="Say yes or no to a circuit",
    description="Each of the three people answers within 72 hours. When all three say yes the circuit becomes active; "
    "one no ends it for everyone. Answering the same way again is safe; changing your answer is a 409; an expired "
    "proposal is a 409.",
)
@require_flag("circuits")
def respond(request, circuit_id: int, body: AnswerIn):
    member = current_member(request)
    if not services.respond(member, circuit_id, body.accept):
        raise Conflict("This proposal has expired", code="circuit_expired")
    return _out(services.get_circuit(member, circuit_id), member)


@router.post(
    "/{circuit_id}/legs/{leg_id}/done",
    response=CircuitOut,
    summary="Mark my handover done",
    description="The person giving says they have done their part. When all three are done the circuit is completed. "
    "Only the giver can do this, and only while the circuit is active. Safe to repeat.",
)
@require_flag("circuits")
def mark_done(request, circuit_id: int, leg_id: int):
    member = current_member(request)
    services.mark_done(member, circuit_id, leg_id)
    return _out(services.get_circuit(member, circuit_id), member)


@router.post(
    "/{circuit_id}/legs/{leg_id}/rating",
    response=CircuitOut,
    summary="Rate what I received",
    description="The person receiving rates the handover from 1 to 5, once it is marked done. The first rating stands.",
)
@require_flag("circuits")
def rate(request, circuit_id: int, leg_id: int, body: RatingIn):
    member = current_member(request)
    services.rate_leg(member, circuit_id, leg_id, body.rating)
    return _out(services.get_circuit(member, circuit_id), member)
