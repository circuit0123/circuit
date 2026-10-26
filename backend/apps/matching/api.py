from typing import Literal

from ninja import Field, Query, Router, Schema

from apps.matching import services
from apps.matching.ranker import snapshots
from core.auth import current_member
from core.pagination import Page, PageParams, paginate

router = Router()


class MatchOut(Schema):
    candidate_id: int
    display_name: str
    role: str
    verification_level: int
    city: str
    sector: str | None
    strength: Literal["strong", "good"] | None  # in words; null when the fit is below "good" (no number is shown)
    reason: str  # one plain sentence, no personal details
    is_bridge: bool  # connects two different sectors
    photo: str | None = None  # signed link, or null
    headline: str  # the first line of their bio (up to 140 characters)
    capabilities: list[str]  # up to 3 things they offer, by name


class MatchParams(PageParams):
    bridge: bool | None = None
    role: Literal["student", "founder", "mentor", "investor"] | None = None
    verified: bool | None = None  # true = verification level 2 or 3
    capability: str | None = Field(None, max_length=100, description="Slug of something they offer")
    within_km: int | None = Field(
        None, description="5, 10, 25 or 50: lives within this distance of my location or the city centre"
    )


@router.get(
    "",
    response=Page[MatchOut],
    summary="My matches",
    description="People who fit what I need and offer, best first, each with a one-line reason. Computed ahead of time, "
    "so this is a cheap read. bridge=true shows only Bridge matches (different sector), bridge=false only the rest. "
    "Filters: role, verified (level 2+), capability (a slug they offer) and within_km (5, 10, 25 or 50). The distance itself is "
    "never returned. Partner admins and super admins have no matches.",
)
def list_matches(request, params: MatchParams = Query(...)):
    member = current_member(request)
    rows = services.matches_for(member, params.bridge, params.role, params.verified, params.capability, params.within_km)
    page = paginate(rows, params)
    snapshots.log_matches(member, [(m["candidate_id"], params.offset + i) for i, m in enumerate(page["items"])])
    return page
