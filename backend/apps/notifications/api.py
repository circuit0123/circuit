from datetime import datetime

from ninja import Query, Router, Schema

from apps.accounts.models import Member
from apps.notifications import copy, services
from apps.notifications.models import Notification
from core.auth import current_member
from core.pagination import Page, PageParams, paginate
from core.schemas import PersonOut, person

router = Router()


class TargetOut(Schema):
    type: str  # intro, application, circuit, conversation, post, startup
    id: int


class NotificationOut(Schema):
    id: int
    kind: str
    text: str  # the one line to show, written from the kind and the actor's current name
    actor: PersonOut | None  # who did it, when a person did
    target: TargetOut | None  # what to open when it is tapped
    payload: dict
    read: bool
    created_at: datetime


class UnreadCountOut(Schema):
    count: int


class NotificationParams(PageParams):
    unread: bool = False


def _nameable(m: Member | None) -> str | None:
    """A second person's name for a line of text. Deleted, suspended and under-18 members are never named."""
    if m is None or m.deleted_at is not None or m.suspended_at is not None or m.is_minor or not m.display_name:
        return None
    return m.display_name


def _ids(rows: list[Notification], key: str) -> set[int]:
    return {n.payload[key] for n in rows if isinstance(n.payload.get(key), int)}


def _lookups(rows: list[Notification]) -> dict:
    """Everything the richer lines need, in one query per kind of thing (never one per row)."""
    from apps.circuits.models import CircuitLeg
    from apps.intros.models import IntroRequest
    from apps.jobs.models import Job
    from apps.startups.models import Startup

    intros = IntroRequest.objects.select_related("requester", "target", "via").in_bulk(_ids(rows, "intro_id"))
    jobs = dict(Job.objects.filter(pk__in=_ids(rows, "job_id")).values_list("pk", "title"))
    startups = dict(Startup.objects.filter(pk__in=_ids(rows, "startup_id")).values_list("pk", "name"))
    legs = dict(CircuitLeg.objects.filter(pk__in=_ids(rows, "leg_id")).values_list("pk", "capability__name"))
    return {"intros": intros, "jobs": jobs, "startups": startups, "legs": legs}


def _rich(n: Notification, look: dict) -> tuple[dict, str | None]:
    """(placeholders, variant) for one notification: who else is involved and what it is about."""
    p = n.payload
    extra: dict = {}
    variant = None
    intro = look["intros"].get(p.get("intro_id"))
    if intro is not None:
        extra = {"target": _nameable(intro.target), "requester": _nameable(intro.requester), "via": _nameable(intro.via)}
        if n.kind == "intro.accepted" and n.member_id == intro.via_id:
            variant = "intro.accepted.broker"
        elif n.kind == "intro.accepted" and p.get("actor_id") == intro.target_id:
            extra = {}  # they accepted themselves: "{who} accepted your introduction." says it all
        elif n.kind == "intro.received" and n.member_id != intro.target_id:
            extra = {}
    if n.kind == "application.status":
        variant = f"application.status.{p.get('status')}"
    extra["job"] = look["jobs"].get(p.get("job_id"))
    extra["startup"] = look["startups"].get(p.get("startup_id"))
    extra["capability"] = look["legs"].get(p.get("leg_id"))
    return {k: v for k, v in extra.items() if v}, variant


def _outs(rows: list[Notification]) -> list[dict]:
    """Serialise a page. Actors and everything the text names are fetched in a few bulk queries, so a card needs no follow-up request."""
    ids = {n.payload.get("actor_id") for n in rows}
    actors = {m.pk: m for m in Member.objects.filter(pk__in={i for i in ids if isinstance(i, int)})}
    look = _lookups(rows)
    result = []
    for n in rows:
        actor = actors.get(n.payload.get("actor_id"))
        extra, variant = _rich(n, look)
        result.append(
            {
                "id": n.pk, "kind": n.kind,
                "text": copy.text(n.kind, actor.display_name if actor else None, extra, variant),
                "actor": person(actor) if actor else None, "target": copy.target(n.kind, n.payload),
                "payload": n.payload, "read": n.read_at is not None, "created_at": n.created_at,
            }
        )  # fmt: skip
    return result


@router.get(
    "",
    response=Page[NotificationOut],
    summary="My notifications",
    description="Newest first. Add unread=true for unread only. Each item has the line to show (`text`), who did it (`actor`) "
    "and what to open (`target`), so the notification centre needs no follow-up calls. Notifications from people I blocked "
    "(or who blocked me) and from features switched off for me are left out.",
)
def list_notifications(request, params: NotificationParams = Query(...)):
    qs = services.visible(current_member(request)).order_by("-created_at", "-id")
    if params.unread:
        qs = qs.filter(read_at__isnull=True)
    page = paginate(qs, params)
    page["items"] = _outs(page["items"])
    return page


@router.get(
    "/unread-count", response=UnreadCountOut, summary="Unread count", description="How many notifications I have not read."
)
def unread_count(request):
    return {"count": services.visible(current_member(request)).filter(read_at__isnull=True).count()}


@router.post(
    "/read-all",
    response=UnreadCountOut,
    summary="Mark all read",
    description="Marks all my notifications read. Returns how many changed.",
)
def read_all(request):
    return {"count": services.mark_all_read(current_member(request))}


@router.post(
    "/{notification_id}/read",
    response=NotificationOut,
    summary="Mark one read",
    description="Marks one of my notifications read. Safe to repeat. Anyone else's id is a 404.",
)
def read_one(request, notification_id: int):
    return _outs([services.mark_read(current_member(request), notification_id)])[0]
