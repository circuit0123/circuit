from ninja import Router, Schema

from apps.dashboard import services
from core.auth import current_member
from core.permissions import require_org_admin

router = Router()


class CountOut(Schema):
    value: int | None  # None when the real number is below 5
    hidden: bool


class GapOut(Schema):
    capability: str
    name: str
    category: str
    needed_by: CountOut  # my members who need it
    offered_by: CountOut  # my members who offer it
    offered_outside: CountOut  # visible people outside the organisation who offer it
    is_gap: bool  # at least 5 members need it and fewer than half as many offer it


class CellOut(Schema):
    lat: float  # centre of the cell
    lng: float
    count: int


class HeatmapOut(Schema):
    cell_degrees: float
    capability: str | None
    cells: list[CellOut]


class NetworkOut(Schema):
    members: CountOut
    new_members_30d: CountOut
    members_with_matches: CountOut
    intros_requested: CountOut
    intros_accepted: CountOut
    circuits_completed: CountOut
    applications: CountOut


class AcceptanceGroup(Schema):
    requested: CountOut
    accepted: CountOut
    rate_percent: int | None  # only when both counts are at least 5


class AcceptanceOut(Schema):
    local: AcceptanceGroup
    bridge: AcceptanceGroup


@router.get(
    "/gaps",
    response=list[GapOut],
    summary="Gap chart",
    description="What my organisation's members need against what they offer, biggest gaps first. Partner admins only, "
    "and only for their own organisation. Counts below 5 are hidden.",
)
def gaps(request):
    return services.gaps(require_org_admin(current_member(request)))


@router.get(
    "/heatmap",
    response=HeatmapOut,
    summary="Where my members are",
    description="Members on a grid of roughly 2 km cells; cells with fewer than 5 members are left out. "
    "Add capability=<slug> to show only members who need that capability.",
)
def heatmap(request, capability: str | None = None):
    return services.heatmap(require_org_admin(current_member(request)), capability)


@router.get(
    "/network",
    response=NetworkOut,
    summary="Network statistics",
    description="Members, new members, matches, introductions, completed circuits and applications for my organisation. "
    "Counts below 5 are hidden.",
)
def network(request):
    return services.network(require_org_admin(current_member(request)))


@router.get(
    "/acceptance",
    response=AcceptanceOut,
    summary="Local vs Bridge introductions",
    description="Introductions my members asked for, split into local and Bridge matches, with how many were accepted. "
    "The rate appears only when both counts are at least 5.",
)
def acceptance(request):
    return services.acceptance(require_org_admin(current_member(request)))
