from datetime import datetime
from typing import Literal

from ninja import Router, Schema, Status
from pydantic import Field

from apps.moderation import services
from core.auth import current_member

router = Router()


class ReportIn(Schema):
    target_type: Literal["post", "reply", "message", "member"]
    target_id: int
    reason: str = Field(min_length=1, max_length=500)


class ReportOut(Schema):
    id: int
    target_type: str
    target_id: int
    status: str
    created_at: datetime


@router.post(
    "",
    response={201: ReportOut},
    summary="Report a post, reply, message or profile",
    description="Goes to the Circuit moderators. You can only report what you can see (anything else is a 404). "
    "Reporting the same thing twice returns the open report.",
)
def create_report(request, body: ReportIn):
    r = services.create_report(current_member(request), body.target_type, body.target_id, body.reason)
    return Status(
        201, {"id": r.pk, "target_type": r.target_type, "target_id": r.target_id, "status": r.status, "created_at": r.created_at}
    )
