"""Exchange circuits (F6): three people in a loop, each giving one thing and receiving another.

A gives B what B needs, B gives C what C needs, C gives A what A needs. The weekly round finds every such loop among
opted-in members, scores each by its weakest handover, and picks the best set of loops where nobody is used twice.
That choice is a small optimisation problem, solved with OR-Tools CP-SAT. Rounds run as a job, never in a request.
"""

from datetime import timedelta

import structlog
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from ortools.sat.python import cp_model

from apps.accounts.models import Member
from apps.circuits.models import Circuit, CircuitLeg, CircuitRound
from apps.events.services import record
from apps.matching import scoring
from apps.matching import services as matching
from apps.notifications.services import notify_many
from apps.social.relations import blocked_ids
from core import realtime
from core.errors import Conflict, Forbidden, NotFound
from core.graph import find_cycles, neighbours
from core.permissions import NETWORK_ROLES

log = structlog.get_logger("circuits")
C, L = Circuit.Status, CircuitLeg.Consent
SOLVER_SECONDS = 10


# -- pure: choosing the loops -----------------------------------------------------------------------
def select_cycles(cycles: list[tuple[tuple[int, ...], float]]) -> list[int]:
    """Indexes of the loops to propose: the highest total score with every member used at most once.

    `cycles` is [(members, score)]. CP-SAT with one worker and a fixed seed, so the same input gives the same answer.
    If the solver cannot answer in time, fall back to taking the best loops greedily.
    """
    if not cycles:
        return []
    model = cp_model.CpModel()
    picks = [model.new_bool_var(f"c{i}") for i in range(len(cycles))]
    by_member: dict[int, list] = {}
    for var, (members, _) in zip(picks, cycles):
        for m in members:
            by_member.setdefault(m, []).append(var)
    for vars_ in by_member.values():
        model.add(sum(vars_) <= 1)
    model.maximize(sum(round(score * 1000) * var for var, (_, score) in zip(picks, cycles)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_SECONDS
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 1
    if solver.solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [i for i, var in enumerate(picks) if solver.value(var)]
    log.warning("circuit_solver_fallback")
    return greedy_cycles(cycles)


def greedy_cycles(cycles: list[tuple[tuple[int, ...], float]]) -> list[int]:
    used: set[int] = set()
    chosen = []
    for i in sorted(range(len(cycles)), key=lambda i: (-cycles[i][1], cycles[i][0])):
        if not used & set(cycles[i][0]):
            chosen.append(i)
            used |= set(cycles[i][0])
    return sorted(chosen)


def weakest_link(edge_scores: dict[tuple[int, int], float], members: tuple[int, ...]) -> float:
    """A loop is only as good as its weakest handover."""
    return min(edge_scores[(members[i], members[(i + 1) % len(members)])] for i in range(len(members)))


# -- the weekly round -----------------------------------------------------------------------------------
def iso_week(now) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _busy_ids() -> set[int]:
    """Members already in a circuit that is still going (proposed or active)."""
    return set(CircuitLeg.objects.filter(circuit__status__in=[C.PROPOSED, C.ACTIVE]).values_list("giver_id", flat=True))


def build_edges(now) -> tuple[dict[tuple[int, int], float], dict[tuple[int, int], str]]:
    """Giver -> receiver edges between opted-in members: the giver offers a capability the receiver needs."""
    world = matching.load_world(now)
    busy = _busy_ids()
    pool = [
        m for m in world.members.values()
        if m.circuits_opt_in and not m.is_minor and m.role in NETWORK_ROLES and m.pk not in busy
    ]  # fmt: skip
    reach = {m.pk: neighbours(m.pk) for m in pool}
    scores: dict[tuple[int, int], float] = {}
    caps: dict[tuple[int, int], str] = {}
    for giver in pool:
        for receiver in pool:
            if giver.pk == receiver.pk:
                continue
            shared = sorted(set(world.sides[giver.pk].offers) & set(world.sides[receiver.pk].needs))
            if not shared:
                continue
            if not (
                matching.allowed(receiver, giver, world, reach[receiver.pk])
                and matching.allowed(giver, receiver, world, reach[giver.pk])
            ):
                continue
            h = reach[receiver.pk].get(giver.pk)
            ps = scoring.score_pair(
                world.sides[receiver.pk], world.sides[giver.pk], (h["hops"], h["strength"]) if h else None,
                settings.MATCH_WEIGHTS, settings.MATCH_MIN_SIMILARITY,
            )  # fmt: skip
            if ps.score >= settings.CIRCUIT_MIN_LEG_SCORE:
                scores[(giver.pk, receiver.pk)], caps[(giver.pk, receiver.pk)] = ps.score, shared[0]
    return scores, caps


def run_round(triggered_by: str = "schedule") -> dict:
    """This week's round. Safe to run again: it only places members who are not already in a circuit."""
    now = timezone.now()
    week = iso_week(now)
    try:
        CircuitRound.objects.get_or_create(week=week, defaults={"triggered_by": triggered_by})
    except IntegrityError:  # another run created it a moment ago
        pass
    with transaction.atomic():
        rnd = CircuitRound.objects.select_for_update().get(week=week)  # a second run waits here, then finds nobody free
        scores, caps = build_edges(now)
        cycles = find_cycles(list(scores), 3)
        scored = [(tuple(c), weakest_link(scores, tuple(c))) for c in cycles]
        created = 0
        for i in select_cycles(scored):
            members, score = scored[i]
            _propose(rnd, members, score, caps, now)
            created += 1
        rnd.status, rnd.finished_at = "done", timezone.now()
        rnd.save(update_fields=["status", "finished_at"])
        summary = {"week": week, "edges": len(scores), "loops_found": len(cycles), "circuits_created": created}
        record(
            "circuit.round_run", triggered_by=triggered_by, edges=len(scores), loops_found=len(cycles), circuits_created=created
        )
    log.info("circuit_round", **summary)
    return summary


def _propose(rnd: CircuitRound, members: tuple[int, ...], score: float, caps: dict, now) -> Circuit:
    from apps.matching.models import Capability

    circuit = Circuit.objects.create(
        round=rnd, score=round(score, 4), consent_deadline=now + timedelta(hours=settings.CIRCUIT_CONSENT_HOURS)
    )
    slug_ids = dict(Capability.objects.filter(slug__in=set(caps.values())).values_list("slug", "id"))
    CircuitLeg.objects.bulk_create(
        CircuitLeg(
            circuit=circuit, giver_id=members[i], receiver_id=members[(i + 1) % 3],
            capability_id=slug_ids[caps[(members[i], members[(i + 1) % 3])]],
        )
        for i in range(3)
    )  # fmt: skip
    record("circuit.proposed", target_type="circuit", target_id=circuit.pk, score=circuit.score)
    notify_many(members, "circuit.proposed", circuit_id=circuit.pk)
    return circuit


# -- expiry and state -------------------------------------------------------------------------------------
def effective_status(circuit: Circuit, now=None) -> str:
    return C.EXPIRED if circuit.status == C.PROPOSED and circuit.consent_deadline <= (now or timezone.now()) else circuit.status


def nudge(circuit_id: int) -> None:
    """Tell the three members' open apps that this circuit changed (ids only; they refetch). Sent after the commit."""
    transaction.on_commit(lambda: realtime.send(f"circuit:{circuit_id}", "status", {"circuit_id": circuit_id}))


def _participants(circuit: Circuit) -> list[int]:
    return list(circuit.legs.values_list("giver_id", flat=True))


def _expire(circuit: Circuit) -> None:
    circuit.status = C.EXPIRED
    circuit.save(update_fields=["status"])
    record("circuit.expired", target_type="circuit", target_id=circuit.pk)
    notify_many(_participants(circuit), "circuit.expired", circuit_id=circuit.pk)
    nudge(circuit.pk)


def expire_due() -> int:
    """The expire_items job: proposals nobody finished answering in 72 hours expire. Safe to run again."""
    n = 0
    for circuit in Circuit.objects.filter(status=C.PROPOSED, consent_deadline__lte=timezone.now()):
        _expire(circuit)
        n += 1
    return n


# -- members' actions ---------------------------------------------------------------------------------------
def my_circuits(member: Member):
    ids = CircuitLeg.objects.filter(giver=member).values("circuit_id")
    qs = Circuit.objects.filter(pk__in=ids)
    blocked = blocked_ids(member.pk)  # a circuit with someone I blocked (or who blocked me) is out of sight, history included
    if blocked:
        qs = qs.exclude(pk__in=CircuitLeg.objects.filter(giver_id__in=blocked).values("circuit_id"))
    return qs.select_related("round").prefetch_related(
        "legs__giver", "legs__receiver", "legs__capability"
    ).order_by("-created_at", "-id")  # fmt: skip


def get_circuit(member: Member, circuit_id: int) -> Circuit:
    """A circuit I am in, else 404: other people's circuits do not exist as far as I can tell."""
    circuit = my_circuits(member).filter(pk=circuit_id).first()
    if circuit is None:
        raise NotFound()
    return circuit


def _locked(member: Member, circuit_id: int) -> Circuit:
    if member.role not in NETWORK_ROLES:
        raise Forbidden()
    circuit = Circuit.objects.select_for_update().filter(pk=circuit_id, legs__giver=member).first()
    if circuit is None:
        raise NotFound()
    return circuit


def respond(member: Member, circuit_id: int, accept: bool) -> bool:
    """Say yes or no to a proposed loop. Returns False if it had already expired (the expiry is saved either way)."""
    with transaction.atomic():
        circuit = _locked(member, circuit_id)
        if circuit.status == C.PROPOSED and circuit.consent_deadline <= timezone.now():
            _expire(circuit)
        if circuit.status == C.EXPIRED:
            return False
        mine = CircuitLeg.objects.get(circuit=circuit, giver=member)  # the leg I give carries my consent
        wanted = L.ACCEPTED if accept else L.DECLINED
        if mine.consent != L.PENDING:
            if mine.consent == wanted:
                return True  # a repeated answer changes nothing
            raise Conflict("You have already answered", code="already_answered")
        if circuit.status != C.PROPOSED:
            raise Conflict("This circuit is no longer waiting for answers", code="circuit_closed")
        mine.consent = wanted
        mine.save(update_fields=["consent"])
        if not accept:
            circuit.status = C.DECLINED
            circuit.save(update_fields=["status"])
            record("circuit.declined", actor=member, target_type="circuit", target_id=circuit.pk)
            notify_many(
                [p for p in _participants(circuit) if p != member.pk], "circuit.declined", actor=member, circuit_id=circuit.pk
            )
            nudge(circuit.pk)
            return True
        record("circuit.accepted", actor=member, target_type="circuit", target_id=circuit.pk)
        nudge(circuit.pk)
        if not circuit.legs.exclude(consent=L.ACCEPTED).exists():
            circuit.status = C.ACTIVE
            circuit.save(update_fields=["status"])
            record("circuit.activated", target_type="circuit", target_id=circuit.pk)
            notify_many(_participants(circuit), "circuit.activated", circuit_id=circuit.pk)
        return True


def _leg(circuit: Circuit, leg_id: int) -> CircuitLeg:
    leg = CircuitLeg.objects.filter(pk=leg_id, circuit=circuit).first()
    if leg is None:
        raise NotFound()
    return leg


def mark_done(member: Member, circuit_id: int, leg_id: int) -> None:
    """The giver says they have handed over what they promised. When all three have, the circuit is complete."""
    with transaction.atomic():
        circuit = _locked(member, circuit_id)
        leg = _leg(circuit, leg_id)
        if leg.giver_id != member.pk:
            raise Forbidden("Only the person giving can mark this done")
        if leg.fulfilled:
            return
        if circuit.status != C.ACTIVE:
            raise Conflict("This circuit is not active", code="circuit_not_active")
        leg.fulfilled = True
        leg.save(update_fields=["fulfilled"])
        nudge(circuit.pk)
        record("circuit.leg_done", actor=member, target_type="circuit", target_id=circuit.pk, leg_id=leg.pk)
        notify_many([leg.receiver_id], "circuit.leg_done", actor=member, circuit_id=circuit.pk, leg_id=leg.pk)
        if not circuit.legs.filter(fulfilled=False).exists():
            circuit.status = C.COMPLETED
            circuit.save(update_fields=["status"])
            record("circuit.completed", target_type="circuit", target_id=circuit.pk)
            notify_many(_participants(circuit), "circuit.completed", circuit_id=circuit.pk)


def rate_leg(member: Member, circuit_id: int, leg_id: int, rating: int) -> None:
    """The receiver rates what they got, 1 to 5, once it has been handed over."""
    with transaction.atomic():
        circuit = _locked(member, circuit_id)
        leg = _leg(circuit, leg_id)
        if leg.receiver_id != member.pk:
            raise Forbidden("Only the person receiving can rate this")
        if leg.rating is not None:
            return  # the first rating stands
        if not leg.fulfilled:
            raise Conflict("Wait until it has been handed over", code="leg_not_done")
        leg.rating = rating
        leg.save(update_fields=["rating"])
        nudge(circuit.pk)
        record("circuit.rated", actor=member, target_type="circuit", target_id=circuit.pk, leg_id=leg.pk, rating=rating)
