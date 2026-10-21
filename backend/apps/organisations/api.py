from ninja import Router, Schema, Status

from apps.accounts.models import Member
from apps.organisations import services
from apps.organisations.models import Organisation
from core.auth import current_context, current_member
from core.errors import NotFound
from core.pagination import Page, PageParams, Query, paginate
from core.permissions import require_org_admin
from core.ratelimit import check_rate

router = Router()


class OrgOut(Schema):
    id: int
    name: str
    kind: str
    city: str
    join_code: str | None = None  # only the organisation's partner admin sees it


class JoinIn(Schema):
    code: str


class OrgMemberOut(Schema):
    id: int
    display_name: str
    role: str
    college: str
    verification_level: int


def _org_out(org: Organisation, member: Member) -> dict:
    is_admin = member.role == "partner_admin" and member.organisation_id == org.pk
    return {"id": org.pk, "name": org.name, "kind": org.kind, "city": org.city, "join_code": org.join_code if is_admin else None}


@router.get("/mine", response=OrgOut, summary="My organisation", description="The organisation I belong to. 404 if none.")
def mine(request):
    member = current_member(request)
    org = Organisation.objects.filter(pk=member.organisation_id).first() if member.organisation_id else None
    if org is None:
        raise NotFound("You are not in an organisation")
    return _org_out(org, member)


@router.post(
    "/join",
    response=OrgOut,
    summary="Join by code",
    description="Join an organisation with its invite code. Students, founders, mentors and investors who are not already in one. Rate limited.",
)
def join(request, body: JoinIn):
    member = current_member(request)
    check_rate(member.pk, "org_join")
    return _org_out(services.join_by_code(member, body.code), member)


@router.post(
    "/join-by-email",
    response=OrgOut,
    summary="Join by verified email domain",
    description="Joins the organisation that owns the domain of the email your sign-in provider verified. The email is read from your token, never from the request.",
)
def join_by_email(request):
    ctx = current_context(request)
    check_rate(ctx.member.pk, "org_join")
    org = services.join_by_email(ctx.member, ctx.verified_email)
    if org is None:  # unreachable (non-quiet raises), but never rely on `assert`, which `python -O` removes
        raise NotFound()
    return _org_out(org, ctx.member)


@router.post("/leave", response={204: None}, summary="Leave my organisation", description="Partner admins cannot leave.")
def leave(request):
    services.leave(current_member(request))
    return Status(204, None)


@router.get(
    "/mine/members",
    response=Page[OrgMemberOut],
    summary="Opted-in members of my organisation",
    description="Partner admins only. Lists members of their own organisation who chose to be visible to it.",
)
def members(request, params: PageParams = Query(...)):
    org_id = require_org_admin(current_member(request))
    qs = Member.objects.filter(organisation_id=org_id, visible_to_org=True).order_by("id")
    return paginate(qs, params)


@router.delete(
    "/mine/members/{member_id}",
    response={204: None},
    summary="Remove a member",
    description="Partner admins only. Removes a member from their own organisation; any other id is a 404.",
)
def remove_member(request, member_id: int):
    admin = current_member(request)
    require_org_admin(admin)
    services.remove_member(admin, member_id)
    return Status(204, None)
