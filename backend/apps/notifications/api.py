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


class CountOut(Schema):
    count: int


class NotificationParams(PageParams):
    unread: bool = False


def _outs(rows: list[Notification]) -> list[dict]:
    """Serialise a page. Actors are fetched in one query, so a card needs no follow-up request."""
    ids = {n.payload.get("actor_id") for n in rows}
    actors = {m.pk: m for m in Member.objects.filter(pk__in={i for i in ids if isinstance(i, int)})}
    result = []
    for n in rows:
        actor = actors.get(n.payload.get("actor_id"))
        result.append(
            {
                "id": n.pk, "kind": n.kind, "text": copy.text(n.kind, actor.display_name if actor else None),
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


@router.get("/unread-count", response=CountOut, summary="Unread count", description="How many notifications I have not read.")
def unread_count(request):
    return {"count": services.visible(current_member(request)).filter(read_at__isnull=True).count()}


@router.post(
    "/read-all",
    response=CountOut,
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
