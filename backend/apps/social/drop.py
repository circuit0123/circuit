"""Daily Drop (F16): three people a day, chosen from the precomputed matches, ready at 08:00 IST.

Finite on purpose (DESIGN.md §8). `build_all` runs as a job; the API only reads. Minors get no drop: a drop exists to
ask for intros, and under-18s cannot send them.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Member
from apps.events.services import record
from apps.matching.services import matches_for
from apps.social import services
from apps.social.models import DailyDrop
from apps.social.relations import SOCIAL_ROLES, connected_ids
from apps.social.schemas import author
from core.errors import ApiError, NotFound

DROP_HOUR = 8
OUTCOMES = ("intro", "skip")


def drop_day(now: datetime) -> date:
    """The drop 'day' starts at 08:00 IST, so before 08:00 you still see yesterday's finished drop."""
    return (now.astimezone(ZoneInfo(settings.DROP_TZ)) - timedelta(hours=DROP_HOUR)).date()


def next_drop_at(now: datetime) -> datetime:
    return datetime.combine(drop_day(now) + timedelta(days=1), time(DROP_HOUR), tzinfo=ZoneInfo(settings.DROP_TZ))


def build_for(member: Member, day: date) -> bool:
    """Create this member's drop for `day`. False if they already have one or nobody qualifies."""
    if DailyDrop.objects.filter(member=member, date=day).exists():
        return False
    recent = {
        c["member_id"]
        for d in DailyDrop.objects.filter(member=member, date__gte=day - timedelta(days=settings.DROP_REPEAT_DAYS))
        for c in d.candidates
    }
    skip = recent | connected_ids(member.pk)
    minors = set(Member.objects.filter(is_minor=True).values_list("pk", flat=True))
    picks = []
    for m in matches_for(member):
        if m["candidate_id"] in skip or m["candidate_id"] in minors or m["role"] not in SOCIAL_ROLES:
            continue
        picks.append({"member_id": m["candidate_id"], "reason": m["reason"], "is_bridge": m["is_bridge"], "outcome": None})
        if len(picks) == settings.DROP_SIZE:
            break
    if not picks:
        return False
    _, created = DailyDrop.objects.get_or_create(member=member, date=day, defaults={"candidates": picks})
    return created


def build_all(now: datetime | None = None) -> dict:
    now = now or timezone.now()
    day = drop_day(now)
    built = skipped = 0
    for member in Member.objects.filter(role__in=SOCIAL_ROLES, is_minor=False, suspended_at__isnull=True).order_by("pk"):
        with transaction.atomic():
            ok = build_for(member, day)
        built += ok
        skipped += not ok
    record("drop.built", day=day.isoformat(), built=built)
    return {"day": day, "built": built, "skipped": skipped}


def today_drop(member: Member) -> dict:
    from apps.social.relations import blocked_ids

    services.require_social(member)
    now = timezone.now()
    drop = DailyDrop.objects.filter(member=member, date=drop_day(now)).first()
    cards = []
    if drop and not member.is_minor:
        hidden = blocked_ids(member.pk)
        people = {
            m.pk: m
            for m in Member.objects.filter(
                pk__in=[c["member_id"] for c in drop.candidates], suspended_at__isnull=True, is_minor=False
            ).exclude(profile_visibility=Member.Visibility.HIDDEN)
        }
        for c in drop.candidates:
            p = people.get(c["member_id"])
            if p is not None and p.pk not in hidden:
                cards.append({"member": author(p), "reason": c["reason"], "is_bridge": c["is_bridge"], "outcome": c["outcome"]})
    return {
        "date": drop.date if drop else drop_day(now), "cards": cards,
        "done": bool(cards) and all(c["outcome"] for c in cards), "next_drop_at": next_drop_at(now),
    }  # fmt: skip


def swipe(member: Member, member_id: int, direction: str) -> dict:
    services.require_social(member)
    if direction not in OUTCOMES:
        raise ApiError(422, "bad_direction", "direction must be intro or skip")
    with transaction.atomic():
        drop = DailyDrop.objects.select_for_update().filter(member=member, date=drop_day(timezone.now())).first()
        card = next((c for c in (drop.candidates if drop else []) if c["member_id"] == member_id), None)
        if drop is None or card is None:
            raise NotFound()
        if card["outcome"] and card["outcome"] != direction:
            raise ApiError(409, "already_answered", "You already answered this card")
        if not card["outcome"]:
            card["outcome"] = direction
            drop.save(update_fields=["candidates"])
            record("drop.swiped", actor=member, target_type="member", target_id=member_id, direction=direction)
    return today_drop(member)
