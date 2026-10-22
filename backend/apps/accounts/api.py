from typing import Literal

from ninja import Router, Schema
from pydantic import Field

from apps.accounts import services
from apps.accounts.models import Member
from apps.matching.models import Capability, MemberSkill, MemberTrait, Need, Offer, Trait
from core.auth import current_member
from core.ratelimit import check_rate

router = Router()
RoleChoice = Literal["student", "founder", "mentor", "investor"]


class MeOut(Schema):
    id: int
    role: str
    display_name: str
    bio: str
    city: str
    college: str
    lat: float | None
    lng: float | None
    verification_level: int
    organisation_id: int | None
    is_minor: bool
    profile_visibility: str
    visible_to_org: bool
    circuits_opt_in: bool
    open_intro_slots: int


class MePatch(Schema):
    display_name: str | None = Field(None, min_length=1, max_length=120)
    bio: str | None = Field(None, max_length=2000)
    city: str | None = Field(None, max_length=100)
    college: str | None = Field(None, max_length=200)
    role: RoleChoice | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    profile_visibility: Literal["public", "members", "hidden"] | None = None
    visible_to_org: bool | None = None
    circuits_opt_in: bool | None = None
    open_intro_slots: int | None = Field(None, ge=0, le=10)


def _me(m: Member) -> dict:
    return {
        "id": m.pk, "role": m.role, "display_name": m.display_name, "bio": m.bio, "city": m.city, "college": m.college,
        "lat": m.location.y if m.location else None, "lng": m.location.x if m.location else None,
        "verification_level": m.verification_level, "organisation_id": m.organisation_id, "is_minor": m.is_minor,
        "profile_visibility": m.profile_visibility, "visible_to_org": m.visible_to_org, "circuits_opt_in": m.circuits_opt_in,
        "open_intro_slots": m.open_intro_slots,
    }  # fmt: skip


@router.get("/me", response=MeOut, summary="Current member", description="The signed-in member's own profile and settings.")
def me(request):
    return _me(current_member(request))


@router.patch(
    "/me",
    response=MeOut,
    summary="Update my profile",
    description="Send only the fields to change. Role may be student, founder, mentor or investor (admin roles are set by Circuit). "
    "Joining circuits needs verification level 2. Under-18 members stay students and are never public.",
)
def update_me(request, body: MePatch):
    member = current_member(request)
    return _me(services.update_profile(member, body.dict(exclude_unset=True)))


# -- lists -------------------------------------------------------------------
class CapabilityOut(Schema):
    slug: str
    name: str
    category: str


class TraitOut(Schema):
    slug: str
    name: str


@router.get(
    "/capabilities",
    response=list[CapabilityOut],
    summary="Capability list",
    description="The fixed list of capabilities used for needs, offers and skills.",
)
def capabilities(request):
    return list(Capability.objects.order_by("category", "name"))


@router.get("/traits", response=list[TraitOut], summary="Trait list", description="The fixed list of traits.")
def traits(request):
    return list(Trait.objects.order_by("name"))


# -- needs, offers, skills, traits ---------------------------------------------------
class NeedOfferIn(Schema):
    capability: str
    description: str = Field("", max_length=500)


class NeedOfferOut(Schema):
    capability: str
    description: str


class SkillIn(Schema):
    capability: str
    level: int = Field(1, ge=1, le=3)
    proof_url: str = Field("", max_length=200)


class SkillOut(Schema):
    capability: str
    level: int
    proof_url: str


def _no(rows) -> list[dict]:
    return [{"capability": r.capability.slug, "description": r.description} for r in rows]


@router.get("/me/needs", response=list[NeedOfferOut], summary="My needs", description="What I am looking for help with.")
def get_needs(request):
    return _no(Need.objects.filter(member=current_member(request)).select_related("capability").order_by("id"))


@router.put(
    "/me/needs",
    response=list[NeedOfferOut],
    summary="Set my needs",
    description="Replaces my needs with this list (max 8, capability slugs from /capabilities). Safe to repeat.",
)
def put_needs(request, body: list[NeedOfferIn]):
    return _no(services.set_needs_or_offers(current_member(request), Need, [b.dict() for b in body]))


@router.get("/me/offers", response=list[NeedOfferOut], summary="My offers", description="What I can help others with.")
def get_offers(request):
    return _no(Offer.objects.filter(member=current_member(request)).select_related("capability").order_by("id"))


@router.put(
    "/me/offers",
    response=list[NeedOfferOut],
    summary="Set my offers",
    description="Replaces my offers with this list (max 8, capability slugs from /capabilities). Safe to repeat.",
)
def put_offers(request, body: list[NeedOfferIn]):
    return _no(services.set_needs_or_offers(current_member(request), Offer, [b.dict() for b in body]))


def _skills(rows) -> list[dict]:
    return [{"capability": r.capability.slug, "level": r.level, "proof_url": r.proof_url} for r in rows]


@router.get(
    "/me/skills", response=list[SkillOut], summary="My skills", description="Skills with level 1-3 and optional proof link."
)
def get_skills(request):
    return _skills(MemberSkill.objects.filter(member=current_member(request)).select_related("capability").order_by("id"))


@router.put(
    "/me/skills",
    response=list[SkillOut],
    summary="Set my skills",
    description="Replaces my skills (max 8). Level 1-3; proof_url is optional proof of work. Safe to repeat.",
)
def put_skills(request, body: list[SkillIn]):
    return _skills(services.set_skills(current_member(request), [b.dict() for b in body]))


@router.get("/me/traits", response=list[str], summary="My traits", description="Trait slugs I picked.")
def get_traits(request):
    rows = MemberTrait.objects.filter(member=current_member(request)).select_related("trait").order_by("id")
    return [r.trait.slug for r in rows]


@router.put(
    "/me/traits",
    response=list[str],
    summary="Set my traits",
    description="Replaces my traits (max 10, slugs from /traits). Safe to repeat.",
)
def put_traits(request, body: list[str]):
    return [r.trait.slug for r in services.set_traits(current_member(request), body)]


# -- public profile -------------------------------------------------------------------------
class ProfileOut(Schema):
    id: int
    role: str
    display_name: str
    bio: str
    city: str
    college: str
    verification_level: int
    needs: list[NeedOfferOut]
    offers: list[NeedOfferOut]
    skills: list[SkillOut]
    traits: list[str]


@router.get(
    "/members/{member_id}",
    response=ProfileOut,
    summary="A member's profile",
    description="Another member's profile. Hidden, under-18, suspended, blocked and admin accounts are a 404.",
)
def member_profile(request, member_id: int):
    target = services.visible_member(current_member(request), member_id)
    return {
        "id": target.pk, "role": target.role, "display_name": target.display_name, "bio": target.bio, "city": target.city,
        "college": target.college, "verification_level": target.verification_level,
        "needs": _no(Need.objects.filter(member=target, is_active=True).select_related("capability").order_by("id")),
        "offers": _no(Offer.objects.filter(member=target, is_active=True).select_related("capability").order_by("id")),
        "skills": _skills(MemberSkill.objects.filter(member=target).select_related("capability").order_by("id")),
        "traits": [t.trait.slug for t in MemberTrait.objects.filter(member=target).select_related("trait").order_by("id")],
    }  # fmt: skip


# -- onboarding --------------------------------------------------------------------------
class ExtractIn(Schema):
    bio: str = Field(min_length=10, max_length=2000)


class Suggestions(Schema):
    needs: list[str]
    offers: list[str]
    skills: list[str]
    traits: list[str]


class ExtractOut(Schema):
    source: Literal["llm", "manual"]
    suggestions: Suggestions


@router.post(
    "/onboarding/extract",
    response=ExtractOut,
    summary="Suggest needs and offers from a bio",
    description="Reads a pasted bio and suggests items from our fixed lists. Nothing is saved: confirm with the PUT endpoints. "
    "If the AI is unavailable, source is 'manual' with empty suggestions and the app shows the pickers. Rate limited.",
)
def extract(request, body: ExtractIn):
    member = current_member(request)
    check_rate(member.pk, "extraction")
    return services.extract_from_bio(member, body.bio)


# -- verification (F7) --------------------------------------------------------------------
class WorkEmailIn(Schema):
    email: str = Field(max_length=254)


class CodeIn(Schema):
    code: str = Field(min_length=4, max_length=16)


class WorkEmailOut(Schema):
    sent: bool
    dev_code: str | None = None  # only in dev and demo, where no real email is sent


@router.post(
    "/me/verify/work-email",
    response=WorkEmailOut,
    summary="Start work-email verification",
    description="Sends a code to a work email (not a personal mailbox). Confirm it to reach verification level 2. Rate limited.",
)
def verify_work_email(request, body: WorkEmailIn):
    member = current_member(request)
    check_rate(member.pk, "verify")
    return {"sent": True, "dev_code": services.start_work_email_check(member, body.email)}


@router.post(
    "/me/verify/work-email/confirm",
    response=MeOut,
    summary="Confirm work-email code",
    description="Enter the code from the email. On success you reach verification level 2.",
)
def verify_work_email_confirm(request, body: CodeIn):
    return _me(services.confirm_work_email(current_member(request), body.code))  # guessing is capped per code, not per day
