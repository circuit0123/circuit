"""Warm intros (F5). A request goes through the best mutual connection first (the broker), then to the target.

Stage says who has to answer: broker -> target -> done. A request that ends before the target saw it is `stopped`,
so the target's inbox only ever shows requests that were vouched for.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import Member
from apps.accounts.services import visible_member
from apps.events.services import record
from apps.intros.models import IntroRequest
from apps.moderation.models import Block
from apps.notifications.services import notify
from apps.social.relations import blocked_ids
from core.errors import ApiError, Conflict, Forbidden, NotFound
from core.graph import neighbours
from core.permissions import NETWORK_ROLES
from core.ratelimit import check_rate

WEEK = timedelta(days=7)
S, G = IntroRequest.Status, IntroRequest.Stage


def effective_status(intro: IntroRequest, now=None) -> str:
    """Reads treat a past-deadline request as expired even before the expire_items job has marked it."""
    return S.EXPIRED if intro.status == S.PENDING and intro.expires_at <= (now or timezone.now()) else intro.status


def can_respond(intro: IntroRequest, member: Member, now=None) -> bool:
    if effective_status(intro, now) != S.PENDING:
        return False
    return (intro.stage == G.BROKER and intro.via_id == member.pk) or (intro.stage == G.TARGET and intro.target_id == member.pk)


def _blocked(a: int, b: int) -> bool:
    return Block.objects.filter(Q(blocker_id=a, blocked_id=b) | Q(blocker_id=b, blocked_id=a)).exists()


def warm_path(member: Member, target_id: int) -> tuple[Member, Member | None]:
    """(target, broker) for the best path of one or two hops. The broker is None when we are already connected."""
    if member.role not in NETWORK_ROLES:
        raise Forbidden()
    target = visible_member(member, target_id)  # hidden, blocked, minor, admin and unknown people are a 404
    if target.pk == member.pk:
        raise ApiError(422, "self_intro", "You cannot ask for an intro to yourself")
    found = neighbours(member.pk).get(target.pk)
    if found is None:
        raise ApiError(404, "no_warm_path", "You have no mutual connection with this person")
    if found["hops"] == 1:
        return target, None
    broker = Member.objects.filter(pk=found["path"][1], suspended_at__isnull=True).first()
    if broker is None or _blocked(broker.pk, member.pk) or _blocked(broker.pk, target.pk):
        raise ApiError(404, "no_warm_path", "You have no mutual connection with this person")
    return target, broker


def _my_recent(member: Member, now):
    return IntroRequest.objects.filter(requester=member, created_at__gte=now - WEEK)


def capacity(member: Member) -> dict:
    """This week's introduction allowance: used, left, and when the next one frees up (the oldest request is a week old).
    Only about me: how full another person is stays private (that is only ever the 409 `target_full`)."""
    limit = settings.INTRO_WEEKLY_LIMIT
    if member.is_minor or member.role not in NETWORK_ROLES:
        return {"allowed": False, "weekly_limit": limit, "used": 0, "left": 0, "next_frees_at": None}
    now = timezone.now()
    created = list(_my_recent(member, now).order_by("created_at").values_list("created_at", flat=True))
    left = max(limit - len(created), 0)
    frees = created[len(created) - limit] + WEEK if left == 0 and created else None  # the one whose week ends first
    return {"allowed": True, "weekly_limit": limit, "used": len(created), "left": left, "next_frees_at": frees}


@transaction.atomic
def request_intro(member: Member, target_id: int, message: str) -> tuple[IntroRequest, bool]:
    """Ask for an intro. Repeating while one is still open returns that request (second item False)."""
    if member.is_minor:
        raise Forbidden("Introductions are not available for under-18 accounts")
    target, broker = warm_path(member, target_id)
    now = timezone.now()
    open_one = IntroRequest.objects.filter(requester=member, target=target, status=S.PENDING, expires_at__gt=now).first()
    if open_one is not None:
        return open_one, False
    check_rate(member.pk, "intro")
    since = now - WEEK
    if _my_recent(member, now).count() >= settings.INTRO_WEEKLY_LIMIT:
        raise Conflict("You have used this week's introductions", code="intro_weekly_limit")
    taken = IntroRequest.objects.filter(
        target=target, created_at__gte=since, status__in=[S.PENDING, S.ACCEPTED, S.COMPLETED]
    ).count()
    if taken >= target.open_intro_slots:
        raise Conflict("This person is not taking more introductions this week", code="target_full")
    intro = IntroRequest.objects.create(
        requester=member, target=target, via=broker, message=message, stage=G.BROKER if broker else G.TARGET,
        path=[member.pk, broker.pk, target.pk] if broker else [member.pk, target.pk],
        expires_at=now + timedelta(days=settings.INTRO_EXPIRY_DAYS),
    )  # fmt: skip
    record("intro.requested", actor=member, target_type="intro", target_id=intro.pk, hops=2 if broker else 1)
    if broker:
        notify(broker, "intro.broker_request", actor=member, intro_id=intro.pk)
    else:
        notify(target, "intro.received", actor=member, intro_id=intro.pk)
    return intro, True


def _expire(intro: IntroRequest) -> None:
    intro.status, intro.stage = S.EXPIRED, G.STOPPED if intro.stage == G.BROKER else G.DONE
    intro.save(update_fields=["status", "stage"])
    record("intro.expired", target_type="intro", target_id=intro.pk)
    notify(intro.requester_id, "intro.expired", intro_id=intro.pk)


def expire_due() -> int:
    """The expire_items job: mark every past-deadline pending request expired. Safe to run again."""
    n = 0
    for intro in IntroRequest.objects.filter(status=S.PENDING, expires_at__lte=timezone.now()):
        _expire(intro)
        n += 1
    return n


def respond(member: Member, intro_id: int, accept: bool) -> IntroRequest:
    """The broker (first) or the target (second) answers. Anyone not in the request gets a 404."""
    if member.role not in NETWORK_ROLES:
        raise Forbidden()
    with transaction.atomic():  # the write that marks it expired must be committed before we refuse
        intro, expired = _respond(member, intro_id, accept)
    if expired:
        raise Conflict("This request has expired", code="intro_expired")
    return intro


def _respond(member: Member, intro_id: int, accept: bool) -> tuple[IntroRequest, bool]:
    intro = IntroRequest.objects.select_for_update().filter(pk=intro_id).first()
    if intro is None or member.pk not in (intro.requester_id, intro.target_id, intro.via_id):
        raise NotFound()
    if intro.status == S.PENDING and intro.expires_at <= timezone.now():
        _expire(intro)
    if intro.status == S.EXPIRED:
        return intro, True
    if can_respond(intro, member):
        _answer(intro, member, accept)
        return intro, False
    is_broker, is_target = intro.via_id == member.pk, intro.target_id == member.pk
    if (is_broker and intro.stage != G.BROKER) or (is_target and intro.stage in (G.DONE, G.STOPPED)):
        return intro, False  # a repeated answer changes nothing
    raise Conflict("It is not your turn to answer this request", code="not_your_turn")


def _answer(intro: IntroRequest, member: Member, accept: bool) -> None:
    now = timezone.now()
    if intro.stage == G.BROKER:
        record("intro.broker_responded", actor=member, target_type="intro", target_id=intro.pk, accepted=accept)
        if accept:
            intro.stage = G.TARGET
            intro.save(update_fields=["stage"])
            notify(intro.requester_id, "intro.vouched", actor=member, intro_id=intro.pk)
            notify(intro.target_id, "intro.received", actor=intro.requester_id, intro_id=intro.pk)
        else:
            intro.status, intro.stage, intro.responded_at = S.DECLINED, G.STOPPED, now
            intro.save(update_fields=["status", "stage", "responded_at"])
            notify(intro.requester_id, "intro.declined", actor=member, intro_id=intro.pk)
        return
    intro.status, intro.stage, intro.responded_at = (S.ACCEPTED if accept else S.DECLINED), G.DONE, now
    intro.save(update_fields=["status", "stage", "responded_at"])
    record("intro.responded", actor=member, target_type="intro", target_id=intro.pk, accepted=accept)
    kind = "intro.accepted" if accept else "intro.declined"
    notify(intro.requester_id, kind, actor=member, intro_id=intro.pk)
    if intro.via_id:
        notify(intro.via_id, kind, actor=member, intro_id=intro.pk)


@transaction.atomic
def rate(member: Member, intro_id: int, rating: int) -> IntroRequest:
    """The requester rates how the introduction went. Only an accepted intro can be rated; repeating changes nothing."""
    intro = IntroRequest.objects.select_for_update().filter(pk=intro_id, requester=member).first()
    if intro is None:
        raise NotFound()
    if intro.status == S.COMPLETED:
        return intro
    if intro.status != S.ACCEPTED:
        raise Conflict("Only an accepted introduction can be rated", code="intro_not_accepted")
    intro.status, intro.outcome_rating = S.COMPLETED, rating
    intro.save(update_fields=["status", "outcome_rating"])
    record("intro.rated", actor=member, target_type="intro", target_id=intro.pk, rating=rating)
    return intro


def inbox(member: Member, box: str) -> QuerySet[IntroRequest]:
    """sent: what I asked for. received: what reached me (vouched for). brokered: where I am the mutual connection."""
    qs = IntroRequest.objects.select_related("requester", "target", "via").order_by("-created_at", "-id")
    blocked = blocked_ids(member.pk)
    if blocked:  # anyone on the request I blocked, or who blocked me, takes the request out of my sight
        qs = qs.exclude(requester_id__in=blocked).exclude(target_id__in=blocked).exclude(via_id__in=blocked)
    if box == "sent":
        return qs.filter(requester=member)
    if box == "received":
        return qs.filter(target=member, stage__in=[G.TARGET, G.DONE])
    return qs.filter(via=member)
