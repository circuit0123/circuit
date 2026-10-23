from datetime import datetime

from ninja import Query, Router, Schema

from apps.notifications import services
from apps.notifications.models import Notification
from core.auth import current_member
from core.pagination import Page, PageParams, paginate

router = Router()


class NotificationOut(Schema):
    id: int
    kind: str
    payload: dict
    read: bool
    created_at: datetime


class CountOut(Schema):
    count: int


class NotificationParams(PageParams):
    unread: bool = False


def _out(n: Notification) -> dict:
    return {"id": n.pk, "kind": n.kind, "payload": n.payload, "read": n.read_at is not None, "created_at": n.created_at}


@router.get(
    "",
    response=Page[NotificationOut],
    summary="My notifications",
    description="Newest first. Add unread=true for unread only. Payloads hold ids only; look details up with the other endpoints.",
)
def list_notifications(request, params: NotificationParams = Query(...)):
    qs = Notification.objects.filter(member=current_member(request)).order_by("-created_at", "-id")
    if params.unread:
        qs = qs.filter(read_at__isnull=True)
    return paginate(qs, params, _out)


@router.get("/unread-count", response=CountOut, summary="Unread count", description="How many notifications I have not read.")
def unread_count(request):
    return {"count": Notification.objects.filter(member=current_member(request), read_at__isnull=True).count()}


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
    return _out(services.mark_read(current_member(request), notification_id))
