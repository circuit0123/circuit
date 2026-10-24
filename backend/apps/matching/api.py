from typing import Literal

from ninja import Query, Router, Schema

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


class MatchParams(PageParams):
    bridge: bool | None = None


@router.get(
    "",
    response=Page[MatchOut],
    summary="My matches",
    description="People who fit what I need and offer, best first, each with a one-line reason. Computed ahead of time, "
    "so this is a cheap read. bridge=true shows only Bridge matches (different sector), bridge=false only the rest. "
    "Partner admins and super admins have no matches.",
)
def list_matches(request, params: MatchParams = Query(...)):
    member = current_member(request)
    page = paginate(services.matches_for(member, params.bridge), params)
    snapshots.log_matches(member, [(m["candidate_id"], params.offset + i) for i, m in enumerate(page["items"])])
    return page
