from ninja import Query, Router, Schema, Status
from pydantic import ConfigDict, Field

from apps.accounts.api import WorkEmailOut
from apps.accounts.models import Role
from apps.social.api import BuildLogTileOut
from apps.startups import services
from core.auth import current_member
from core.permissions import require_role
from core.ratelimit import check_rate
from core.schemas import PersonOut

router = Router()


class PinOut(Schema):
    id: int
    name: str
    lat: float
    lng: float
    hiring: bool
    sector: str
    claimed: bool
    open_roles: int
    match_pct: int | None = None  # students only; None when the startup has no open role
    distance_km: float | None = None
    logo: str | None = None  # signed link, or null (draw the circuit-pattern square)


class NearbyParams(Schema):
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    radius_km: float = Field(10, gt=0, le=services.MAX_RADIUS_KM)
    hiring: bool | None = None
    capability: str | None = Field(None, max_length=100)
    limit: int = Field(50, ge=1, le=200)


class BboxParams(Schema):
    min_lng: float = Field(ge=-180, le=180)
    min_lat: float = Field(ge=-90, le=90)
    max_lng: float = Field(ge=-180, le=180)
    max_lat: float = Field(ge=-90, le=90)
    hiring: bool | None = None
    capability: str | None = Field(None, max_length=100)


@router.get(
    "/nearby",
    response=list[PinOut],
    summary="Startups near a point",
    description="Nearest first. Defaults to my saved location, else the city centre. Filters: hiring, capability of an open role, radius.",
)
def nearby(request, params: NearbyParams = Query(...)):
    p = params
    return services.nearby(current_member(request), p.lat, p.lng, p.radius_km, p.hiring, p.capability, p.limit)


@router.get(
    "/map",
    response=list[PinOut],
    summary="Startups in a map box",
    description="Pins inside a bounding box (max about 2 degrees wide, max 500 pins). Hiring startups come first.",
)
def map_pins(request, params: BboxParams = Query(...)):
    p = params
    return services.in_bbox(current_member(request), p.min_lng, p.min_lat, p.max_lng, p.max_lat, p.hiring, p.capability)


class OpenJobOut(Schema):
    id: int
    title: str
    kind: str
    stipend_min: int | None
    stipend_max: int | None


class FounderOut(Schema):
    person: PersonOut
    role: str
    via: PersonOut | None  # the mutual connection who would introduce me; null when connected, none, or I am under 18
    connected: bool
    is_me: bool


class StartupOut(Schema):
    id: int
    name: str
    website_domain: str
    description: str
    sector: str
    stage: str
    address: str
    team_size: int | None
    logo: str | None
    lat: float | None
    lng: float | None
    hiring: bool
    tech_stack: list[str]
    claimed: bool
    verified: bool  # claimed through a company email on the startup's own domain
    source: str
    view_count: int | None  # private: the startup's team, or a founder looking at an unclaimed page (not under 5). Else null
    interest_count: int | None  # same rule
    interested: bool
    is_team: bool
    match_pct: int | None
    open_jobs: list[OpenJobOut]
    founders: list[FounderOut]
    build_logs: list[BuildLogTileOut]  # empty when Pulse is off for me


class StartupPatch(Schema):
    description: str | None = Field(None, max_length=3000)
    stage: str | None = Field(None, max_length=40)
    hiring: bool | None = None
    address: str | None = Field(None, max_length=300)
    tech_stack: list[str] | None = Field(None, max_length=20)
    team_size: int | None = Field(None, ge=1, le=10000)
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)


@router.get(
    "/{startup_id}",
    response=StartupOut,
    summary="Startup profile",
    description="Profile, open roles, founders (each with the warm path to them), the latest build log pictures and the logo. Counts one view per member per day. "
    "`view_count` and `interest_count` are private: only the startup's team, or a founder looking at an unclaimed page (a reason to claim it, never under 5), get them. "
    "Members under 18 see an unverified startup as not hiring, with no roles.",
)
def startup_detail(request, startup_id: int):
    member = current_member(request)
    return services.detail(member, services.get_startup(startup_id))


@router.patch(
    "/{startup_id}",
    response=StartupOut,
    summary="Edit my startup",
    description="Only the team of a claimed startup. Claimed data is never overwritten by anything else.",
)
def update_startup(request, startup_id: int, body: StartupPatch):
    member = current_member(request)
    startup = services.update_startup(member, services.get_startup(startup_id), body.dict(exclude_unset=True))
    return services.detail(member, startup, count_view=False)


class LogoIn(Schema):
    model_config = ConfigDict(extra="forbid")
    upload_id: int


@router.put(
    "/{startup_id}/logo",
    response=StartupOut,
    summary="Set the startup's logo",
    description="The startup's team only. Upload the image first (`POST /api/media/uploads` with purpose `startup_logo`, founders only), "
    "then send its id. The previous logo is deleted.",
)
def set_logo(request, startup_id: int, body: LogoIn):
    member = current_member(request)
    check_rate(member.pk, "settings_write")
    startup = services.set_logo(member, services.get_startup(startup_id), body.upload_id)
    return services.detail(member, startup, count_view=False)


@router.delete(
    "/{startup_id}/logo",
    response=StartupOut,
    summary="Remove the startup's logo",
    description="The startup's team only. Safe to repeat.",
)
def remove_logo(request, startup_id: int):
    member = current_member(request)
    check_rate(member.pk, "settings_write")
    startup = services.set_logo(member, services.get_startup(startup_id), None)
    return services.detail(member, startup, count_view=False)


@router.post(
    "/{startup_id}/interest",
    response={204: None},
    summary="I'm interested",
    description="Students only. Tells the startup I'm interested. Safe to repeat.",
)
def add_interest(request, startup_id: int):
    member = current_member(request)
    require_role(member, Role.STUDENT)
    services.add_interest(member, services.get_startup(startup_id))
    return Status(204, None)


@router.delete(
    "/{startup_id}/interest", response={204: None}, summary="Withdraw interest", description="Students only. Safe to repeat."
)
def remove_interest(request, startup_id: int):
    member = current_member(request)
    require_role(member, Role.STUDENT)
    services.remove_interest(member, services.get_startup(startup_id))
    return Status(204, None)


class ClaimIn(Schema):
    email: str = Field(max_length=254)


class ClaimConfirmIn(Schema):
    code: str = Field(min_length=4, max_length=16)


@router.post(
    "/{startup_id}/claim",
    response=WorkEmailOut,
    summary="Start claiming a startup",
    description="Founders only. Sends a code to an email at the startup's own website domain. Rate limited. In dev and demo the code is returned.",
)
def start_claim(request, startup_id: int, body: ClaimIn):
    member = current_member(request)
    require_role(member, Role.FOUNDER)
    check_rate(member.pk, "claim")
    startup = services.get_startup(startup_id)
    return {"sent": True, "dev_code": services.start_claim(member, startup, body.email)}


@router.post(
    "/{startup_id}/claim/verify",
    response=StartupOut,
    summary="Finish claiming a startup",
    description="Founders only. Enter the emailed code to become the startup's owner (also raises you to verification level 2). Rate limited.",
)
def verify_claim(request, startup_id: int, body: ClaimConfirmIn):
    member = current_member(request)
    require_role(member, Role.FOUNDER)
    check_rate(member.pk, "claim")
    startup = services.verify_claim(member, startup_id, body.code)
    return services.detail(member, startup, count_view=False)
