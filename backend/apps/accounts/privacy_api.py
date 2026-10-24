"""Data requests (DPDP): export, delete and write to support. Correction is the normal profile edit (PATCH /api/me)."""

from datetime import datetime
from typing import Literal

from ninja import Router, Schema, Status
from pydantic import Field

from apps.accounts import deletion, export, support
from apps.accounts.settings_api import ExportStatus, SupportOut, support_info
from core.auth import current_member

router = Router()


class DownloadOut(Schema):
    url: str  # a storage link that works for a few minutes
    expires_in: int
    size_bytes: int


class DeletionIn(Schema):
    confirm: Literal["DELETE"]  # the app makes the person type it


class DeletionOut(Schema):
    status: Literal["scheduled"]
    requested_at: datetime


class SupportIn(Schema):
    kind: Literal["question", "correction", "data_request", "grievance"]
    message: str = Field(min_length=5, max_length=2000)


class SupportReceipt(Schema):
    reference: str


@router.get(
    "/me/export",
    response=ExportStatus | None,
    summary="My latest data export",
    description="Status of my most recent export (pending, building, ready, failed, expired), or null if I never asked. "
    "Open to members who have not accepted the latest policy or have no beta access.",
)
def my_export(request):
    return export.latest(current_member(request))


@router.post(
    "/me/export",
    response={202: ExportStatus},
    summary="Ask for a copy of my data",
    description="Starts an export of only my own data (profile, posts, messages I sent, connections, circuits and more) as a zip. "
    "A job builds it and emails a link that works for 24 hours. One at a time (409 `export_in_progress`); 3 a day.",
)
def request_export(request):
    return Status(202, export.request_export(current_member(request)))


@router.get(
    "/me/export/download",
    response=DownloadOut,
    summary="Get the download link for my export",
    description="Send the `token` from the email link while signed in as the same member. Returns a storage link that works for a "
    "few minutes. Someone else's token is a 404; an old one is 410 `export_expired`.",
)
def download_export(request, token: str):
    return export.download(current_member(request), token)


@router.post(
    "/me/deletion",
    response={202: DeletionOut},
    summary="Delete my account",
    description='Send {"confirm": "DELETE"}. The account is locked at once (every call answers 403 `account_deleted`) and a job '
    'removes the sign-in, files, profile, needs, offers and connections, and shows old posts and messages as "Deleted member". '
    "Payment records are kept as tax law requires. Startups I claimed pass to another team member or become unclaimed. "
    "Safe to repeat. Circuit admins cannot delete themselves here.",
)
def delete_account(request, body: DeletionIn):
    member = deletion.request_deletion(current_member(request))
    return Status(202, {"status": "scheduled", "requested_at": member.deletion_requested_at})


@router.post(
    "/support",
    response={202: SupportReceipt},
    summary="Write to support or the grievance officer",
    description="A question, a correction, a data request or a grievance. Emails the right inbox and sends me an acknowledgement "
    "with a reference. 5 a day. Open to members who have not accepted the latest policy or have no beta access.",
)
def write_support(request, body: SupportIn):
    return Status(202, {"reference": support.submit(current_member(request), body.kind, body.message)})


@router.get(
    "/support/contact",
    auth=None,
    response=SupportOut,
    summary="Support and grievance contacts",
    description="Public. The support address and the grievance officer's name, email and address (from settings), for the legal "
    "pages and the Help screen.",
)
def contact(request):
    return support_info()
