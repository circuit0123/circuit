from ninja import Query, Router, Schema

from apps.matching import services
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
    score_percent: int  # 0 to 100
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
    return paginate(services.matches_for(current_member(request), params.bridge), params)
