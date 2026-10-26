from datetime import date, datetime
from typing import Literal

from ninja import Query, Router, Schema, Status
from pydantic import Field

from apps.accounts.models import Role
from apps.jobs import services
from apps.jobs.models import Application
from apps.matching.models import MemberSkill
from core.auth import current_member
from core.pagination import Page, PageParams, paginate
from core.permissions import require_role
from core.schemas import PersonOut

router = Router()
Kind = Literal["internship", "full_time", "part_time"]


class JobCapabilityOut(Schema):
    slug: str
    name: str
    required: bool
    your_level: int | None = None  # students only on the job page: my level in it, or None if I lack it


class JobOut(Schema):
    id: int
    title: str
    kind: str
    description: str
    stipend_min: int | None
    stipend_max: int | None
    location: str
    is_open: bool
    created_at: datetime
    startup_id: int
    startup_name: str
    sector: str
    startup_verified: bool  # claimed with a company email; members under 18 only ever see roles from verified startups
    startup_logo: str | None
    duration_weeks: int | None
    starts_on: date | None
    contact: PersonOut | None  # the founder who claimed the startup: who "We'll tell you when X replies" means
    is_team: bool  # I am on this startup's team: show "See applicants" instead of "Apply"
    lat: float | None
    lng: float | None
    distance_km: float | None
    capabilities: list[JobCapabilityOut]
    skill_match: float | None = None  # 0..1, students only
    applied: bool | None = None  # students only


class JobCapabilityIn(Schema):
    capability: str
    required: bool = True


class JobIn(Schema):
    startup_id: int
    title: str = Field(min_length=3, max_length=200)
    kind: Kind = "internship"
    description: str = Field("", max_length=5000)
    stipend_min: int | None = Field(None, ge=0, le=10_000_000)
    stipend_max: int | None = Field(None, ge=0, le=10_000_000)
    location: str = Field("", max_length=200)
    duration_weeks: int | None = Field(None, ge=1, le=520)
    starts_on: date | None = None
    capabilities: list[JobCapabilityIn] = Field(min_length=1, max_length=services.MAX_JOB_CAPABILITIES)


class JobPatch(Schema):
    title: str | None = Field(None, min_length=3, max_length=200)
    kind: Kind | None = None
    description: str | None = Field(None, max_length=5000)
    stipend_min: int | None = Field(None, ge=0, le=10_000_000)
    stipend_max: int | None = Field(None, ge=0, le=10_000_000)
    location: str | None = Field(None, max_length=200)
    duration_weeks: int | None = Field(None, ge=1, le=520)
    starts_on: date | None = None
    is_open: bool | None = None
    capabilities: list[JobCapabilityIn] | None = Field(None, min_length=1, max_length=services.MAX_JOB_CAPABILITIES)


class JobFilters(PageParams):
    kind: Kind | None = None
    capability: str | None = Field(None, max_length=100)
    startup_id: int | None = None
    max_distance_km: float | None = Field(None, gt=0, le=200)
    min_stipend: int | None = Field(None, ge=0)


@router.get(
    "/jobs",
    response=Page[JobOut],
    summary="Open jobs",
    description="Open jobs with filters (kind, capability, startup, distance from my location or the city centre, minimum stipend). "
    "Students get skill_match (0 to 1) and the best match first; everyone else gets newest first.",
)
def list_jobs(request, params: JobFilters = Query(...)):
    return services.list_jobs_page(current_member(request), params.dict(exclude={"limit", "offset"}), params.offset, params.limit)


class SkillDemandOut(Schema):
    slug: str
    name: str
    open_roles: int


class SkillsParams(Schema):
    within_km: float = Field(10, gt=0, le=100)


@router.get(
    "/jobs/skills-in-demand",
    response=list[SkillDemandOut],
    summary="Skills in demand near me",
    description="The top 3 capabilities asked for by open roles within `within_km` (default 10) of my location or the city centre. "
    "Role counts only, never people. Members under 18 count only verified startups' roles.",
)
def skills_in_demand(request, params: SkillsParams = Query(...)):
    return services.skills_in_demand(current_member(request), params.within_km)


@router.get(
    "/jobs/{job_id}",
    response=JobOut,
    summary="Job page",
    description="One job. Students see their skill match and which required skills they have. A closed job is visible to its team only.",
)
def job_page(request, job_id: int):
    member = current_member(request)
    return services.job_detail(member, services.get_visible_job(member, job_id))


@router.post(
    "/jobs",
    response=JobOut,
    summary="Post a job",
    description="Founders on a claimed startup's team. Needs 1 to 8 capabilities from the fixed list. Marks the startup as hiring.",
)
def create_job(request, body: JobIn):
    member = current_member(request)
    require_role(member, Role.FOUNDER)
    data = body.dict(exclude={"startup_id", "capabilities"})
    job = services.create_job(member, body.startup_id, data, [c.dict() for c in body.capabilities])
    return services.job_detail(member, services.get_visible_job(member, job.pk))


@router.patch(
    "/jobs/{job_id}",
    response=JobOut,
    summary="Edit or close a job",
    description="The startup's team only. Set is_open to false to close it. Changing capabilities re-scores existing applications.",
)
def update_job(request, job_id: int, body: JobPatch):
    member = current_member(request)
    require_role(member, Role.FOUNDER)
    changes = body.dict(exclude_unset=True, exclude={"capabilities"})
    caps = [c.dict() for c in body.capabilities] if body.capabilities is not None else None
    services.update_job(member, job_id, changes, caps)
    return services.job_detail(member, services.get_visible_job(member, job_id))


# -- applications ---------------------------------------------------------------------------
class ApplicationOut(Schema):
    id: int
    job_id: int
    job_title: str
    startup_id: int
    startup_name: str
    status: str
    skill_match: float
    created_at: datetime


class ApplicantSkill(Schema):
    capability: str  # the capability's slug
    name: str  # the same capability's display name
    level: int
    proof_url: str


class ApplicantOut(Schema):
    application_id: int
    student_id: int
    display_name: str
    status: str
    skill_match: float
    skills: list[ApplicantSkill]
    applied_at: datetime


class StatusIn(Schema):
    status: Literal["shortlisted", "rejected", "hired"]


def _application(a: Application) -> dict:
    return {
        "id": a.pk, "job_id": a.job_id, "job_title": a.job.title, "startup_id": a.job.startup_id, "startup_name": a.job.startup.name,
        "status": a.status, "skill_match": a.skill_match, "created_at": a.created_at,
    }  # fmt: skip


@router.post(
    "/jobs/{job_id}/apply",
    response={200: ApplicationOut, 201: ApplicationOut},
    summary="Apply to a job",
    description="Students only, one click. 201 for a new application, 200 if I had already applied (safe to repeat). "
    "A withdrawn application is reopened. Closed jobs are a 409. Rate limited.",
)
def apply(request, job_id: int):
    member = current_member(request)
    require_role(member, Role.STUDENT)
    app, created = services.apply(member, job_id)
    app = Application.objects.select_related("job__startup").get(pk=app.pk)
    return Status(201 if created else 200, _application(app))


@router.get(
    "/me/applications",
    response=Page[ApplicationOut],
    summary="My applications",
    description="Students: my applications with their status, newest first.",
)
def my_applications(request, params: PageParams = Query(...)):
    member = current_member(request)
    require_role(member, Role.STUDENT)
    return paginate(services.my_applications(member), params, _application)


@router.post(
    "/applications/{application_id}/withdraw",
    response=ApplicationOut,
    summary="Withdraw an application",
    description="Students only, my own application. Safe to repeat. Decided applications are a 409.",
)
def withdraw(request, application_id: int):
    member = current_member(request)
    require_role(member, Role.STUDENT)
    app = services.withdraw(member, application_id)
    return _application(Application.objects.select_related("job__startup").get(pk=app.pk))


@router.get(
    "/jobs/{job_id}/applicants",
    response=Page[ApplicantOut],
    summary="Applicants for my job",
    description="The startup's team only. Ranked by skill match, then earliest application. College is not shown or used.",
)
def applicants(request, job_id: int, params: PageParams = Query(...)):
    member = current_member(request)
    require_role(member, Role.FOUNDER)
    _, qs = services.applicants(member, job_id)
    page = paginate(qs, params)
    by_student: dict[int, list[MemberSkill]] = {}
    ids = [a.student_id for a in page["items"]]
    for s in MemberSkill.objects.filter(member_id__in=ids).select_related("capability").order_by("-level", "id"):
        by_student.setdefault(s.member_id, []).append(s)  # one query for the whole page, not one per applicant
    page["items"] = [
        {
            "application_id": a.pk, "student_id": a.student_id, "display_name": a.student.display_name, "status": a.status,
            "skill_match": a.skill_match, "applied_at": a.created_at,
            "skills": [
                {"capability": s.capability.slug, "name": s.capability.name, "level": s.level, "proof_url": s.proof_url}
                for s in by_student.get(a.student_id, [])
            ],
        }
        for a in page["items"]
    ]  # fmt: skip
    return page


@router.patch(
    "/applications/{application_id}",
    response=ApplicationOut,
    summary="Shortlist, reject or hire",
    description="The startup's team only. applied can become shortlisted or rejected; shortlisted can become hired or rejected. "
    "Other people's applications are a 404. The student is notified.",
)
def set_status(request, application_id: int, body: StatusIn):
    member = current_member(request)
    require_role(member, Role.FOUNDER)
    app = services.set_status(member, application_id, body.status)
    return _application(Application.objects.select_related("job__startup").get(pk=app.pk))
