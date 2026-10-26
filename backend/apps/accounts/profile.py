"""The Profile screen in one response (DESIGN.md §4 "Profile"): header, actions, needs and offers, build logs, circuits, about.

Rules the screen relies on: no follower or connection counts (only "N mutual connections", which is about me and them); the
strength meter and the exact circuit history belong to the owner; a connection sees how many circuits were closed, a stranger sees
nothing about circuits, and the circuits two people are both in are only their shared history. What a viewer may do with this person (connect, message, ask for an intro) is decided here, once, from the
same rules the endpoints enforce, so the screen never has to guess.
"""

from apps.accounts import highlights
from apps.accounts.models import ConnectionRequest, Member, Role
from apps.matching.models import MemberSkill, Need, Offer
from apps.social import media
from apps.social.relations import connected_ids, is_connected, may_message, may_request_connection, same_org
from core import flags, ist
from core.permissions import NETWORK_ROLES
from core.schemas import person

MAX_TILES = 12
STRENGTH_STEPS = (
    ("photo", "Add a photo"),
    ("headline", "Add a headline under your name"),
    ("bio", "Write a line about what you do"),
    ("offers", "Add something you can offer"),
    ("needs", "Add something you need"),
    ("skills", "Add a skill with a link to your work"),
    ("verified", "Verify your work email"),
    ("post", "Share your first build log"),
)


def connection_state(viewer: Member, target: Member) -> str:
    if viewer.pk == target.pk:
        return "self"
    if is_connected(viewer.pk, target.pk):
        return "connected"
    pending = ConnectionRequest.objects.filter(status=ConnectionRequest.Status.PENDING)
    if pending.filter(sender=viewer, recipient=target).exists():
        return "requested"  # I asked them
    if pending.filter(sender=target, recipient=viewer).exists():
        return "requested_you"  # they asked me
    return "none"  # a declined request looks like none: the sender is never told


def actions(viewer: Member, target: Member, state: str, via: Member | None) -> dict:
    if state == "self":
        return {"connect": False, "message": False, "intro": False}
    recently_declined = ConnectionRequest.objects.filter(
        sender=viewer, recipient=target, status=ConnectionRequest.Status.DECLINED
    ).exists()  # the exact re-ask window is enforced when asking; the screen just does not offer it
    return {
        "connect": state in ("none", "requested_you") and not recently_declined and may_request_connection(viewer, target),
        "message": may_message(viewer, target),
        "intro": via is not None and not viewer.is_minor and viewer.role in NETWORK_ROLES,
    }


def strength(member: Member) -> dict:
    """How complete my own profile is, and the one thing to do next. Owner only."""
    from apps.social.models import Post

    done = {
        "photo": bool(member.photo_path),
        "headline": bool(member.headline.strip()),
        "bio": len((member.bio or "").strip()) >= 20,
        "offers": Offer.objects.filter(member=member, is_active=True).exists(),
        "needs": Need.objects.filter(member=member, is_active=True).exists(),
        "skills": MemberSkill.objects.filter(member=member).exclude(proof_url="").exists(),
        "verified": member.verification_level >= 2,
        "post": Post.objects.filter(author=member).exists(),
    }
    steps = [(k, text) for k, text in STRENGTH_STEPS if k != "post" or flags.enabled("pulse", member)]
    left = [(k, text) for k, text in steps if not done[k]]
    nxt = {"key": left[0][0], "text": left[0][1]} if left else None
    return {"percent": round(100 * (len(steps) - len(left)) / len(steps)), "next_step": nxt}


def circuits_closed(target: Member) -> int:
    from apps.circuits.models import Circuit, CircuitLeg

    return Circuit.objects.filter(
        status=Circuit.Status.COMPLETED, pk__in=CircuitLeg.objects.filter(giver=target).values("circuit")
    ).count()


def circuits_together(viewer: Member, target: Member) -> list[dict]:
    """Circuits that both of us are in and that are running or finished (a proposal, a no or a lapse is never shown), newest first.
    It is only my own history with them, so it tells a stranger nothing."""
    from apps.circuits.models import Circuit, CircuitLeg

    mine = CircuitLeg.objects.filter(giver=viewer).values("circuit")
    theirs = CircuitLeg.objects.filter(giver=target).values("circuit")
    done = (Circuit.Status.ACTIVE, Circuit.Status.COMPLETED)
    rows = Circuit.objects.filter(pk__in=mine, status__in=done).filter(pk__in=theirs).order_by("-created_at", "-id")[:MAX_TILES]
    return [
        {"id": c.pk, "month": ist.local(c.created_at).strftime("%Y-%m"), "completed": c.status == Circuit.Status.COMPLETED}
        for c in rows
    ]


def header(viewer: Member, target: Member) -> dict:
    """Everything the Profile screen adds to the basic profile fields."""
    from apps.intros.services import warm_path
    from apps.social.services import picture_tiles
    from core.errors import ApiError

    me = viewer.pk == target.pk
    state = connection_state(viewer, target)
    via = None
    if not me and state != "connected" and not viewer.is_minor and viewer.role in NETWORK_ROLES:
        try:
            _, via = warm_path(viewer, target.pk)
        except ApiError:  # no mutual connection: no intro button
            via = None
    media.prime_photos([m for m in (target, via) if m is not None])
    friends = state == "connected"
    out = {
        "is_me": me,
        "photo": media.own_photo(target) if me else media.photo_of(target),
        "headline": target.headline_line(),
        "organisation": target.organisation.name if target.organisation and (me or same_org(viewer, target)) else None,
        "connection": state,
        "actions": actions(viewer, target, state, via),
        "mutual_count": None if me else len(connected_ids(viewer.pk) & connected_ids(target.pk)),
        "via": person(via) if via is not None else None,
        "build_logs": picture_tiles(viewer, [target.pk], MAX_TILES) if target.role in Role.values else [],
        "circuits_closed": circuits_closed(target) if (me or friends) and flags.enabled("circuits", viewer) else None,
        "circuits_together": circuits_together(viewer, target) if not me and flags.enabled("circuits", viewer) else None,
        "highlights": highlights.rows_for(viewer, target),
        "strength": strength(target) if me else None,
    }
    return out
