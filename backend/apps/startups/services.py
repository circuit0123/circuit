"""Startup rules: map and nearby search, views and interest, profile edits, and the claim flow (F2, F3)."""

import math
from collections.abc import Sequence
from datetime import timedelta
from typing import cast

import structlog
from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Count, F, QuerySet
from django.utils import timezone

from apps.accounts.models import Member, Role
from apps.accounts.services import raise_level
from apps.events.services import record
from apps.jobs.models import Job, JobCapability
from apps.matching.models import MemberSkill
from apps.matching.scoring import skill_match
from apps.notifications.services import notify, notify_many
from apps.startups.models import ClaimRequest, Startup, StartupInterest, StartupMember
from core import codes
from core.cache import get_cache
from core.errors import ApiError, Conflict, Forbidden, NotFound

log = structlog.get_logger("startups")

CLAIM_TTL = timedelta(hours=24)
MAX_PINS = 500
MAX_BBOX_DEGREES = 2.0  # about 220 km: a city and its surroundings, not the country
MAX_RADIUS_KM = 100
EDITABLE = {"description", "stage", "hiring", "address", "tech_stack"}


# -- search ----------------------------------------------------------------------------------
def _filtered(hiring: bool | None, capability: str | None) -> QuerySet[Startup]:
    qs = Startup.objects.filter(location__isnull=False, hidden_at__isnull=True)  # a reported startup a moderator hid is gone
    if hiring is not None:
        qs = qs.filter(hiring=hiring)
    if capability:
        qs = qs.filter(jobs__is_open=True, jobs__capabilities__capability__slug=capability).distinct()
    return qs


def _open_roles(startup_ids: list[int]) -> dict[int, int]:
    rows = Job.objects.filter(startup_id__in=startup_ids, is_open=True).values("startup_id").annotate(n=Count("id"))
    return {r["startup_id"]: r["n"] for r in rows}


def student_match_pcts(member: Member, startup_ids: list[int]) -> dict[int, int]:
    """Skill match 0-100 per startup, from that startup's open jobs. Only for students; startups with no open role are absent."""
    if member.role != Role.STUDENT or not startup_ids:
        return {}
    skills = {s.capability_id: s.level for s in MemberSkill.objects.filter(member=member)}
    required: dict[int, set[int]] = {}
    optional: dict[int, set[int]] = {}
    rows = JobCapability.objects.filter(job__startup_id__in=startup_ids, job__is_open=True).values_list(
        "job__startup_id", "capability_id", "required"
    )
    for sid, cap, req in rows:
        (required if req else optional).setdefault(sid, set()).add(cap)
    out = {}
    for sid in set(required) | set(optional):
        out[sid] = round(100 * skill_match(skills, required.get(sid, set()), optional.get(sid, set()) - required.get(sid, set())))
    return out


def _pin(s: Startup, roles: dict[int, int], pcts: dict[int, int]) -> dict:
    loc = cast(Point, s.location)  # every search filters on location__isnull=False
    return {
        "id": s.pk, "name": s.name, "lat": loc.y, "lng": loc.x, "hiring": s.hiring, "sector": s.sector,
        "claimed": s.claimed_by_id is not None, "open_roles": roles.get(s.pk, 0), "match_pct": pcts.get(s.pk),
    }  # fmt: skip


def _pins(member: Member, startups: Sequence[Startup]) -> list[dict]:
    ids = [s.pk for s in startups]
    roles, pcts = _open_roles(ids), student_match_pcts(member, ids)
    return [_pin(s, roles, pcts) for s in startups]


def default_centre(member: Member) -> tuple[float, float]:
    if member.location:
        return float(member.location.y), float(member.location.x)
    return cast(float, settings.SEED_CITY["lat"]), cast(float, settings.SEED_CITY["lng"])


def nearby(member: Member, lat: float | None, lng: float | None, radius_km: float, hiring, capability, limit: int) -> list[dict]:
    if lat is None or lng is None:
        lat, lng = default_centre(member)
    radius_km = min(radius_km, MAX_RADIUS_KM)
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    box = Polygon.from_bbox((lng - dlng, lat - dlat, lng + dlng, lat + dlat))
    box.srid = 4326
    centre = Point(lng, lat, srid=4326)
    qs = (
        _filtered(hiring, capability)
        .filter(location__intersects=box)  # uses the GIST index; the exact distance check comes next
        .annotate(dist=Distance("location", centre))
        .filter(dist__lte=D(km=radius_km))
        .order_by("dist", "id")[:limit]
    )
    rows = list(qs)
    pins = _pins(member, rows)
    for pin, s in zip(pins, rows):
        pin["distance_km"] = round(s.dist.km, 2)
    return pins


def in_bbox(member: Member, min_lng: float, min_lat: float, max_lng: float, max_lat: float, hiring, capability) -> list[dict]:
    if min_lng >= max_lng or min_lat >= max_lat:
        raise ApiError(422, "invalid_bbox", "The box must have min below max")
    if max_lng - min_lng > MAX_BBOX_DEGREES or max_lat - min_lat > MAX_BBOX_DEGREES:
        raise ApiError(422, "bbox_too_large", "Zoom in: that map area is too large")
    box = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
    box.srid = 4326
    rows = list(_filtered(hiring, capability).filter(location__intersects=box).order_by("-hiring", "id")[:MAX_PINS])
    return _pins(member, rows)


# -- detail, views, interest --------------------------------------------------------------------
def is_team(member: Member, startup: Startup) -> bool:
    return startup.claimed_by_id is not None and StartupMember.objects.filter(startup=startup, member=member).exists()


def team_member_ids(startup: Startup) -> list[int]:
    ids = set(StartupMember.objects.filter(startup=startup).values_list("member_id", flat=True))
    if startup.claimed_by_id:
        ids.add(startup.claimed_by_id)
    return sorted(ids)


def startup_id_of(member: Member) -> int | None:
    """The startup this member is on (a listed team member, else the one they claimed); the first if several."""
    on_team = (
        StartupMember.objects.filter(member=member).order_by("created_at", "id").values_list("startup_id", flat=True).first()
    )
    if on_team is not None:
        return on_team
    return Startup.objects.filter(claimed_by=member, hidden_at__isnull=True).order_by("id").values_list("pk", flat=True).first()


def get_startup(startup_id: int) -> Startup:
    s = Startup.objects.filter(pk=startup_id, hidden_at__isnull=True).first()
    if s is None:
        raise NotFound()
    return s


def detail(member: Member, startup: Startup, count_view: bool = True) -> dict:
    if count_view and not is_team(member, startup):
        _count_view(member, startup)
    jobs = list(Job.objects.filter(startup=startup, is_open=True).order_by("-created_at"))
    pct = student_match_pcts(member, [startup.pk]).get(startup.pk)
    return {
        "id": startup.pk, "name": startup.name, "website_domain": startup.website_domain, "description": startup.description,
        "sector": startup.sector, "stage": startup.stage, "address": startup.address,
        "lat": startup.location.y if startup.location else None, "lng": startup.location.x if startup.location else None,
        "hiring": startup.hiring, "tech_stack": startup.tech_stack, "claimed": startup.claimed_by_id is not None,
        "source": startup.source, "view_count": startup.view_count,
        "interest_count": StartupInterest.objects.filter(startup=startup).count(),
        "interested": StartupInterest.objects.filter(startup=startup, member=member).exists(),
        "is_team": is_team(member, startup), "match_pct": pct,
        "open_jobs": [
            {"id": j.pk, "title": j.title, "kind": j.kind, "stipend_min": j.stipend_min, "stipend_max": j.stipend_max}
            for j in jobs
        ],
    }  # fmt: skip


def _count_view(member: Member, startup: Startup) -> None:
    """One view per member per day. If Redis is down we count anyway: a slightly high number beats a failed page."""
    day = timezone.now().date().isoformat()
    n = get_cache().incr_window(f"view:{startup.pk}:{member.pk}:{day}", 86400)
    if n is None or n == 1:
        Startup.objects.filter(pk=startup.pk).update(view_count=F("view_count") + 1)
        startup.refresh_from_db(fields=["view_count"])
        record("startup.viewed", actor=member, target_type="startup", target_id=startup.pk)


def add_interest(member: Member, startup: Startup) -> None:
    _, created = StartupInterest.objects.get_or_create(startup=startup, member=member)
    if created:
        record("startup.interest_added", actor=member, target_type="startup", target_id=startup.pk)
        notify_many(team_member_ids(startup), "startup.interest", startup_id=startup.pk)


def remove_interest(member: Member, startup: Startup) -> None:
    deleted, _ = StartupInterest.objects.filter(startup=startup, member=member).delete()
    if deleted:
        record("startup.interest_removed", actor=member, target_type="startup", target_id=startup.pk)


# -- editing ---------------------------------------------------------------------------------
def update_startup(member: Member, startup: Startup, changes: dict) -> Startup:
    """Only the team of a claimed startup edits it. Nothing else (crawler, seed) ever overwrites claimed data."""
    if not is_team(member, startup):
        raise Forbidden("Only the startup's team can edit it")
    lat, lng = changes.pop("lat", None), changes.pop("lng", None)
    if (lat is None) != (lng is None):
        raise ApiError(422, "validation_error", "Send both lat and lng, or neither")
    if lat is not None and lng is not None:
        startup.location = Point(lng, lat, srid=4326)
    for field, value in changes.items():
        if field in EDITABLE:
            setattr(startup, field, value)
    startup.save()
    record("startup.updated", actor=member, target_type="startup", target_id=startup.pk, fields=sorted(changes))
    return startup


# -- claim flow (F3) -----------------------------------------------------------------------------
def _domain_belongs(email_domain: str, website_domain: str) -> bool:
    site = website_domain.lower().removeprefix("www.")
    return email_domain == site or email_domain.endswith("." + site)


def start_claim(member: Member, startup: Startup, email: str) -> str | None:
    if startup.claimed_by_id is not None:
        raise Conflict("This startup has already been claimed", code="already_claimed")
    domain = codes.email_domain(email)
    if not domain or not _domain_belongs(domain, startup.website_domain):
        raise ApiError(422, "email_domain_mismatch", "Use an email address at the startup's own website domain")
    code = codes.new_code()
    ClaimRequest.objects.filter(startup=startup, member=member, status=ClaimRequest.Status.PENDING).delete()
    ClaimRequest.objects.create(
        startup=startup,
        member=member,
        email_domain=domain,
        token_hash=codes.hash_code(code),
        expires_at=timezone.now() + CLAIM_TTL,
    )
    dev_code = codes.send_code(email.strip(), code, "claiming your startup")
    record("startup.claim_started", actor=member, target_type="startup", target_id=startup.pk)
    return dev_code


@transaction.atomic
def verify_claim(member: Member, startup_id: int, code: str) -> Startup:
    startup = Startup.objects.select_for_update().filter(pk=startup_id).first()
    if startup is None:
        raise NotFound()
    if startup.claimed_by_id is not None:
        raise Conflict("This startup has already been claimed", code="already_claimed")
    req = (
        ClaimRequest.objects.filter(
            startup=startup, member=member, status=ClaimRequest.Status.PENDING, expires_at__gt=timezone.now()
        )
        .order_by("-id")
        .first()
    )
    if req is None or not codes.code_matches(code, req.token_hash):
        raise ApiError(400, "code_invalid", "That code is wrong or has expired")
    req.status = ClaimRequest.Status.VERIFIED
    req.save(update_fields=["status"])
    ClaimRequest.objects.filter(startup=startup, status=ClaimRequest.Status.PENDING).update(status=ClaimRequest.Status.EXPIRED)
    startup.claimed_by, startup.claimed_at = member, timezone.now()
    startup.save(update_fields=["claimed_by", "claimed_at"])
    StartupMember.objects.get_or_create(startup=startup, member=member, defaults={"role": "founder"})
    raise_level(member, 2, reason="startup_claim")
    record("startup.claimed", actor=member, target_type="startup", target_id=startup.pk)
    notify(member, "startup.claimed", startup_id=startup.pk)
    return startup


def on_startup_unclaimed(startup: Startup, transferred_to: int | None = None) -> None:
    """Called when the member who claimed a startup is deleted: `transferred_to` is the new owner, or None if it is now unclaimed.

    HOOK FOR STAGE 4d (promotions): pause every active campaign of this startup here, because the person who bought it is gone.
    Orders and payments are never touched (they are kept for the tax period, Stage 4e). Nothing to do until campaigns exist."""
    log.info("startup_owner_removed", startup_id=startup.pk, transferred=transferred_to is not None)


def expire_claims() -> int:
    return ClaimRequest.objects.filter(status=ClaimRequest.Status.PENDING, expires_at__lte=timezone.now()).update(
        status=ClaimRequest.Status.EXPIRED
    )
