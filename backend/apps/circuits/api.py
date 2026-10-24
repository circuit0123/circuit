from datetime import datetime

from ninja import Field, Query, Router, Schema

from apps.circuits import services
from apps.circuits.models import Circuit
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
    fulfilled: bool
    rating: int | None
    i_give: bool  # I can mark this done
    i_receive: bool  # I can rate this once it is done


class CircuitOut(Schema):
    id: int
    status: str  # proposed, active, completed, expired, declined
    score_percent: int  # the weakest handover in the loop
    week: str
    consent_deadline: datetime
    created_at: datetime
    my_consent: str
    legs: list[LegOut]


class AnswerIn(Schema):
    accept: bool


class RatingIn(Schema):
    rating: int = Field(ge=1, le=5)


def _out(c: Circuit, me) -> dict:
    legs = sorted(c.legs.all(), key=lambda leg: leg.pk)
    mine = next(leg for leg in legs if leg.giver_id == me.pk)
    return {
        "id": c.pk, "status": services.effective_status(c), "score_percent": round(c.score * 100), "week": c.round.week,
        "consent_deadline": c.consent_deadline, "created_at": c.created_at, "my_consent": mine.consent,
        "legs": [
            {
                "id": leg.pk, "giver": person(leg.giver), "receiver": person(leg.receiver), "capability": leg.capability.name,
                "consent": leg.consent, "fulfilled": leg.fulfilled, "rating": leg.rating, "i_give": leg.giver_id == me.pk,
                "i_receive": leg.receiver_id == me.pk,
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
    description="Exchange circuits I am part of, newest first, with live status: who gives what to whom, who has said "
    "yes, what has been handed over. A proposal nobody finished answering in 72 hours reads as expired.",
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
    description="A circuit I am part of. Anyone else's circuit is a 404.",
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
