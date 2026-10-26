"""Jobs and applications (F11). Skill match decides ranking: the applicant's college is never used."""

from collections.abc import Callable
from typing import cast

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Q, QuerySet

from apps.accounts.models import Member, Role
from apps.events.services import record
from apps.jobs.models import Application, Job, JobCapability
from apps.matching.models import Capability, MemberSkill
from apps.matching.scoring import skill_match
from apps.notifications.services import notify, notify_many
from apps.social import media
from apps.startups.models import Startup, StartupMember
from apps.startups.services import default_centre, get_startup, is_team, is_verified, minor_blocked, team_member_ids
from core.errors import ApiError, Conflict, Forbidden, NotFound
from core.ratelimit import check_rate
from core.schemas import person

MAX_JOB_CAPABILITIES = 8
MAX_LISTED_JOBS = 500  # students get a skill-ranked list, so we rank at most this many in memory
STATUS_FLOW = {
    Application.Status.APPLIED: {Application.Status.SHORTLISTED, Application.Status.REJECTED},
    Application.Status.SHORTLISTED: {Application.Status.HIRED, Application.Status.REJECTED},
}
STUDENT_CAN_WITHDRAW = {Application.Status.APPLIED, Application.Status.SHORTLISTED}


# -- helpers ----------------------------------------------------------------------------------
def student_skills(member: Member) -> dict[int, int]:
    return {s.capability_id: s.level for s in MemberSkill.objects.filter(member=member)}


def job_match(skills: dict[int, int], job: Job) -> float:
    caps = list(job.capabilities.all())  # prefetched by callers that list many jobs
    required = {c.capability_id for c in caps if c.required}
    optional = {c.capability_id for c in caps if not c.required}
    return skill_match(skills, required, optional)


def get_job_for_team(member: Member, job_id: int) -> Job:
    """A job the member's team owns. Unknown id is a 404; a real job of someone else's startup is a 403."""
    job = Job.objects.select_related("startup").filter(pk=job_id).first()
    if job is None:
        raise NotFound()
    if not is_team(member, job.startup):
        raise Forbidden("Only the startup's team can do this")
    return job


def get_visible_job(member: Member, job_id: int) -> Job:
    """Open jobs are public to signed-in members; a closed job is visible to its team only."""
    job = Job.objects.select_related("startup__claimed_by").prefetch_related("capabilities__capability").filter(pk=job_id).first()
    if job is None or ((not job.is_open or job.startup.hidden_at is not None) and not is_team(member, job.startup)):
        raise NotFound()
    if minor_blocked(member, job.startup):
        raise NotFound()  # under-18: roles at unverified startups do not exist
    return job


def _set_capabilities(job: Job, items: list[dict]) -> None:
    seen: dict[str, bool] = {}
    for it in items:
        seen.setdefault(it["capability"], it["required"])
    if not seen or len(seen) > MAX_JOB_CAPABILITIES:
        raise ApiError(422, "validation_error", f"A job needs 1 to {MAX_JOB_CAPABILITIES} capabilities")
    caps = {c.slug: c for c in Capability.objects.filter(slug__in=seen)}
    unknown = sorted(set(seen) - set(caps))
    if unknown:
        raise ApiError(422, "unknown_capability", "Unknown capability", {"slugs": unknown})
    JobCapability.objects.filter(job=job).delete()
    JobCapability.objects.bulk_create(JobCapability(job=job, capability=caps[s], required=req) for s, req in seen.items())


def _check_stipend(lo, hi) -> None:
    if lo is not None and hi is not None and lo > hi:
        raise ApiError(422, "validation_error", "stipend_min cannot be above stipend_max")


# -- listing ---------------------------------------------------------------------------------
def _open_jobs(member: Member, f: dict) -> tuple[list[Job], dict[int, int] | None]:
    """Open jobs, filtered, in the order members see them: students best skill match first, everyone else newest first."""
    qs: QuerySet[Job] = (
        Job.objects.filter(is_open=True, startup__hidden_at__isnull=True)
        .select_related("startup__claimed_by")
        .prefetch_related("capabilities__capability")
    )
    if member.is_minor:
        qs = qs.filter(startup__claimed_by__isnull=False)  # under-18: verified (claimed) startups only
    if f.get("kind"):
        qs = qs.filter(kind=f["kind"])
    if f.get("startup_id"):
        qs = qs.filter(startup_id=f["startup_id"])
    if f.get("since"):
        qs = qs.filter(created_at__gte=f["since"])
    if f.get("q"):
        qs = qs.filter(
            Q(title__icontains=f["q"]) | Q(startup__name__icontains=f["q"]) | Q(capabilities__capability__name__icontains=f["q"])
        )
    if f.get("capability"):
        qs = qs.filter(capabilities__capability__slug=f["capability"])
    if f.get("min_stipend") is not None:
        qs = qs.filter(Q(stipend_max__gte=f["min_stipend"]) | Q(stipend_max__isnull=True, stipend_min__gte=f["min_stipend"]))
    lat, lng = default_centre(member)
    centre = Point(lng, lat, srid=4326)
    qs = qs.annotate(dist=Distance("startup__location", centre))
    if f.get("max_distance_km") is not None:
        from django.contrib.gis.measure import D

        qs = qs.filter(startup__location__isnull=False, dist__lte=D(km=f["max_distance_km"]))
    jobs: list[Job] = list(qs.order_by("-created_at", "-id").distinct()[:MAX_LISTED_JOBS])
    skills = student_skills(member) if member.role == Role.STUDENT else None
    if skills is not None:
        jobs.sort(key=lambda j: -job_match(skills, j))  # stable: ties keep newest first
    return jobs, skills


def _job_rows(member: Member, jobs: list[Job], skills: dict[int, int] | None) -> list[dict]:
    """The full rows, built only for the jobs that are going to be shown."""
    applied = (
        set(Application.objects.filter(student=member, job__in=jobs).exclude(status="withdrawn").values_list("job_id", flat=True))
        if skills is not None
        else set()
    )
    team = _team_startups(member)
    media.prime_logos(j.startup for j in jobs)
    media.prime_photos(j.startup.claimed_by for j in jobs if j.startup.claimed_by is not None)
    return [_job_row(j, skills, applied, team) for j in jobs]


def list_jobs(member: Member, f: dict, keep: Callable[[Job, dict[int, int] | None], bool] | None = None) -> list[dict]:
    """Every open job matching the filters as full rows (for callers that look at all of them: Pulse, Live wire).

    `keep(job, skills)` drops jobs before their rows are built, so a caller that wants a handful does not pay for hundreds."""
    jobs, skills = _open_jobs(member, f)
    if keep is not None:
        jobs = [j for j in jobs if keep(j, skills)]
    return _job_rows(member, jobs, skills)


def list_jobs_page(member: Member, f: dict, offset: int, limit: int) -> dict:
    """One page of the jobs list. The order and the count cover every match, but rows are built for the page only."""
    jobs, skills = _open_jobs(member, f)
    nxt = offset + limit
    return {
        "items": _job_rows(member, jobs[offset:nxt], skills),
        "count": len(jobs),
        "next_offset": nxt if nxt < len(jobs) else None,
    }


def _team_startups(member: Member) -> set[int]:
    return set(StartupMember.objects.filter(member=member).values_list("startup_id", flat=True))


def _job_row(job: Job, skills: dict[int, int] | None, applied: set[int] | None = None, team: set[int] | None = None) -> dict:
    dist = getattr(job, "dist", None)
    owner = job.startup.claimed_by
    loc = cast(Point | None, job.startup.location)
    return {
        "id": job.pk, "title": job.title, "kind": job.kind, "description": job.description, "stipend_min": job.stipend_min,
        "stipend_max": job.stipend_max, "location": job.location, "is_open": job.is_open, "created_at": job.created_at,
        "startup_id": job.startup_id, "startup_name": job.startup.name, "sector": job.startup.sector,
        "startup_verified": is_verified(job.startup), "startup_logo": media.logo_of(job.startup),
        "duration_weeks": job.duration_weeks, "starts_on": job.starts_on,
        "contact": person(owner) if owner is not None and owner.deleted_at is None else None,
        "is_team": owner is not None and job.startup_id in (team or set()),
        "lat": loc.y if loc else None, "lng": loc.x if loc else None,
        "distance_km": round(dist.km, 2) if dist is not None else None,
        "capabilities": [{"slug": c.capability.slug, "name": c.capability.name, "required": c.required} for c in job.capabilities.all()],
        "skill_match": job_match(skills, job) if skills is not None else None,
        "applied": (job.pk in applied) if applied is not None and skills is not None else None,
    }  # fmt: skip


def job_detail(member: Member, job: Job) -> dict:
    skills = student_skills(member) if member.role == Role.STUDENT else None
    applied = None
    if skills is not None:
        applied = set(
            Application.objects.filter(student=member, job=job).exclude(status="withdrawn").values_list("job_id", flat=True)
        )
    media.prime_logos([job.startup])
    row = _job_row(job, skills, applied, _team_startups(member))
    if skills is not None:
        row["capabilities"] = [
            {**c, "your_level": skills.get(cap.capability_id)} for c, cap in zip(row["capabilities"], job.capabilities.all())
        ]
    return row


def skills_in_demand(member: Member, within_km: float, since=None, limit: int = 3) -> list[dict]:
    """The capabilities most asked for by open roles within `within_km` of me: role counts only, never people. Members under 18
    count only verified startups' roles."""
    lat, lng = default_centre(member)
    centre = Point(lng, lat, srid=4326)
    qs = JobCapability.objects.filter(
        job__is_open=True,
        job__startup__hidden_at__isnull=True,
        job__startup__location__distance_lte=(centre, D(km=within_km)),
    )
    if since is not None:
        qs = qs.filter(job__created_at__gte=since)
    if member.is_minor:
        qs = qs.filter(job__startup__claimed_by__isnull=False)
    counts: dict[str, tuple[str, int]] = {}
    for slug, name in qs.values_list("capability__slug", "capability__name"):
        counts[slug] = (name, counts.get(slug, (name, 0))[1] + 1)
    top = sorted(counts.items(), key=lambda kv: (-kv[1][1], kv[0]))[:limit]
    return [{"slug": slug, "name": name, "open_roles": n} for slug, (name, n) in top]


# -- posting -------------------------------------------------------------------------------------
@transaction.atomic
def create_job(member: Member, startup_id: int, data: dict, capabilities: list[dict]) -> Job:
    startup = get_startup(startup_id)
    if not is_team(member, startup):
        raise Forbidden("Only the startup's team can post jobs")
    _check_stipend(data.get("stipend_min"), data.get("stipend_max"))
    job = Job.objects.create(startup=startup, posted_by=member, **data)
    _set_capabilities(job, capabilities)
    if not startup.hiring:
        Startup.objects.filter(pk=startup.pk).update(hiring=True)  # an open role means the startup is hiring
    record("job.created", actor=member, target_type="job", target_id=job.pk, startup_id=startup.pk)
    return job


@transaction.atomic
def update_job(member: Member, job_id: int, changes: dict, capabilities: list[dict] | None) -> Job:
    job = get_job_for_team(member, job_id)
    merged = {"stipend_min": job.stipend_min, "stipend_max": job.stipend_max, **changes}
    _check_stipend(merged["stipend_min"], merged["stipend_max"])
    for field, value in changes.items():
        setattr(job, field, value)
    job.save()
    if capabilities is not None:
        _set_capabilities(job, capabilities)
        _refresh_scores(job)
    if not Job.objects.filter(startup=job.startup, is_open=True).exists():
        Startup.objects.filter(pk=job.startup_id).update(hiring=False)
    elif job.is_open:
        Startup.objects.filter(pk=job.startup_id).update(hiring=True)
    record(
        "job.updated",
        actor=member,
        target_type="job",
        target_id=job.pk,
        fields=sorted(changes) + (["capabilities"] if capabilities is not None else []),
    )
    return job


def _refresh_scores(job: Job) -> None:
    """When the requirements change, applications are re-scored against the new ones."""
    job = Job.objects.prefetch_related("capabilities").get(pk=job.pk)
    for app in Application.objects.filter(job=job).select_related("student"):
        app.skill_match = job_match(student_skills(app.student), job)
        app.save(update_fields=["skill_match", "updated_at"])


# -- applying ------------------------------------------------------------------------------------
def apply(member: Member, job_id: int) -> tuple[Application, bool]:
    """Apply to an open job. Repeating returns the same application (second item False); a withdrawn one is reopened."""
    job = Job.objects.select_related("startup").prefetch_related("capabilities").filter(pk=job_id).first()
    if job is None or minor_blocked(member, job.startup):
        raise NotFound()
    existing = Application.objects.filter(job=job, student=member).first()
    if existing is not None and existing.status != Application.Status.WITHDRAWN:
        return existing, False
    if not job.is_open:
        raise Conflict("This job is closed", code="job_closed")
    check_rate(member.pk, "application")  # only real new applications count against the limit
    score = job_match(student_skills(member), job)
    with transaction.atomic():
        if existing is None:
            app = Application.objects.create(job=job, student=member, skill_match=score)
        else:
            app = existing
            app.status, app.skill_match = Application.Status.APPLIED, score
            app.save(update_fields=["status", "skill_match", "updated_at"])
        record(
            "application.created",
            actor=member,
            target_type="application",
            target_id=app.pk,
            job_id=job.pk,
            reapplied=existing is not None,
        )
        notify_many(
            team_member_ids(job.startup),
            "application.received",
            actor=member,
            application_id=app.pk,
            job_id=job.pk,
            startup_id=job.startup_id,
        )
    return app, True


def withdraw(member: Member, application_id: int) -> Application:
    app = Application.objects.filter(pk=application_id, student=member).first()
    if app is None:
        raise NotFound()
    if app.status == Application.Status.WITHDRAWN:
        return app  # safe to repeat
    if app.status not in STUDENT_CAN_WITHDRAW:
        raise Conflict("This application is already decided", code="application_decided")
    app.status = Application.Status.WITHDRAWN
    app.save(update_fields=["status", "updated_at"])
    record("application.withdrawn", actor=member, target_type="application", target_id=app.pk, job_id=app.job_id)
    return app


def my_applications(member: Member) -> QuerySet[Application]:
    return Application.objects.filter(student=member).select_related("job__startup").order_by("-created_at", "-id")


def applicants(member: Member, job_id: int) -> tuple[Job, QuerySet[Application]]:
    """Applicants for one of the team's jobs, best skill match first (ties: earliest). Withdrawn ones are left out."""
    job = get_job_for_team(member, job_id)
    qs = (
        Application.objects.filter(job=job)
        .exclude(status=Application.Status.WITHDRAWN)
        .select_related("student")
        .order_by("-skill_match", "created_at", "id")
    )
    return job, qs


def set_status(member: Member, application_id: int, new_status: str) -> Application:
    """Founders move applications along. An application on someone else's job is a plain 404 (ids are private)."""
    app = Application.objects.select_related("job__startup").filter(pk=application_id).first()
    if app is None or not is_team(member, app.job.startup):
        raise NotFound()
    if new_status not in STATUS_FLOW.get(Application.Status(app.status), set()):
        raise Conflict(f"An application that is {app.status} cannot become {new_status}", code="invalid_transition")
    old = app.status
    app.status = new_status
    app.save(update_fields=["status", "updated_at"])
    record("application.status_changed", actor=member, target_type="application", target_id=app.pk, old=old, new=new_status)
    notify(app.student_id, "application.status", actor=member, application_id=app.pk, job_id=app.job_id, status=new_status)
    return app
