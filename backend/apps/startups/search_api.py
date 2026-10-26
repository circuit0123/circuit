from ninja import Field, Query, Router, Schema

from apps.jobs.api import JobOut
from apps.social.schemas import AuthorOut
from apps.startups import search
from apps.startups.api import PinOut
from core.auth import current_member

router = Router()


class SearchParams(Schema):
    q: str = Field(min_length=2, max_length=100)


class SearchOut(Schema):
    people: list[AuthorOut]
    startups: list[PinOut]
    jobs: list[JobOut]


@router.get(
    "",
    response=SearchOut,
    summary="Search people, startups and roles",
    description="One call for the Discover search field: up to 10 people (by name), 10 startups (by name or sector) and 10 roles "
    "(by title, startup or skill). Hidden, under-18, blocked and deleted people never appear; members under 18 find only their "
    "connections and roles at verified startups. Rate limited.",
)
def search_all(request, params: SearchParams = Query(...)):
    return search.search(current_member(request), params.q)
