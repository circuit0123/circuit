from ninja import Router, Schema

from core.auth import current_member

router = Router()


class MeOut(Schema):
    id: int
    role: str
    display_name: str
    verification_level: int
    organisation_id: int | None
    is_minor: bool


@router.get("/me", response=MeOut, summary="Current member", description="The signed-in member's own basics.")
def me(request):
    return current_member(request)
