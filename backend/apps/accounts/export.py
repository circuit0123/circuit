"""Data export (DPDP right to access): everything Circuit holds about ONE member, as a zip they can download.

Request (`POST /api/me/export`) -> the `build_exports` job builds `data.json` plus their media files and stores the zip in the
private bucket -> an email carries a signed link that works for 24 hours -> the app trades the link for a short storage URL.

What goes in: rows the member wrote or owns. Other people appear as ids only; what other people wrote to the member (their
messages, request notes, intro messages) stays out, and so do recommendations Circuit computed (matches, Daily Drop reasons).
"""

import io
import json
import zipfile
from datetime import timedelta
from uuid import uuid4

import structlog
from django.conf import settings
from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Connection, ConnectionRequest, Consent, DataExport, Member, WorkEmailVerification
from apps.beta.models import BetaAccess, InviteCode
from apps.circuits.models import CircuitLeg
from apps.events.models import Event
from apps.events.services import record
from apps.intros.models import IntroRequest
from apps.jobs.models import Application, Job
from apps.matching.models import MemberSkill, MemberTrait, Need, Offer
from apps.messaging.models import Conversation, Message
from apps.moderation.models import Block, Report
from apps.notifications.models import Notification
from apps.social.models import DailyDrop, Follow, MediaUpload, Post, PostMedia, Reaction, Reply
from apps.startups.models import Startup, StartupInterest, StartupMember
from core import email as outbox
from core.errors import ApiError, Conflict, NotFound
from core.ratelimit import check_rate
from core.storage import get_storage

log = structlog.get_logger("export")

SALT = "circuit.export.v1"
MAX_ATTEMPTS = 3
MAX_MEDIA_BYTES = 200 * 1024 * 1024  # a zip stays emailable-sized in spirit; the rest is listed as skipped
README = (
    "This is the data Circuit holds about you.\n\n"
    "data.json: your profile, needs, offers, posts, replies, reactions, connections, messages you sent, applications, "
    "circuits, notifications, reports, blocks, consents and the product events recorded about your actions.\n"
    "media/: the pictures you uploaded.\n\n"
    "Other people appear as numbers only. What other people wrote to you (their messages and notes) and recommendations "
    "we computed for you (matches, Daily Drop) are not included.\n"
    "Questions or corrections: see the contact details in the app, under Settings.\n"
)


def _rows(qs, *fields) -> list[dict]:
    return list(qs.values(*fields))


def member_data(member: Member) -> dict:
    """Everything in data.json. Only ever called with the signed-in member's own row."""
    me = member.pk
    sent_to = Conversation.objects.filter(Q(member_a=member) | Q(member_b=member))
    conversations = []
    for c in sent_to.order_by("id"):
        conversations.append(
            {
                "id": c.pk, "with_member_id": c.member_b_id if c.member_a_id == me else c.member_a_id, "status": c.status,
                "started_by_me": c.started_by_id == me, "created_at": c.created_at,
                "messages_sent": [
                    {"id": m["id"], "body": "" if m["removed_at"] else m["body"], "created_at": m["created_at"]}
                    for m in Message.objects.filter(conversation=c, sender=member).order_by("id").values(
                        "id", "body", "removed_at", "created_at"
                    )
                ],
            }
        )  # fmt: skip
    legs = []
    for leg in CircuitLeg.objects.filter(Q(giver=member) | Q(receiver=member)).select_related("capability").order_by("id"):
        gives = leg.giver_id == me
        legs.append(
            {
                "circuit_id": leg.circuit_id, "i_give": gives, "other_member_id": leg.receiver_id if gives else leg.giver_id,
                "capability": leg.capability.slug, "my_consent": leg.consent if gives else None,
                "done": leg.fulfilled, "my_rating": None if gives else leg.rating,
            }
        )  # fmt: skip
    drops = [
        {"date": d.date, "cards": [{"member_id": c.get("member_id"), "outcome": c.get("outcome")} for c in d.candidates]}
        for d in DailyDrop.objects.filter(member=member).order_by("date")
    ]
    return {
        "exported_at": timezone.now(),
        "profile": {
            "id": me, "role": member.role, "display_name": member.display_name, "email": member.email, "bio": member.bio,
            "city": member.city, "college": member.college, "organisation_id": member.organisation_id,
            "latitude": member.location.y if member.location else None, "longitude": member.location.x if member.location else None,
            "verification_level": member.verification_level, "is_minor": member.is_minor,
            "profile_visibility": member.profile_visibility, "visible_to_org": member.visible_to_org,
            "circuits_opt_in": member.circuits_opt_in, "allow_requests": member.allow_requests,
            "open_intro_slots": member.open_intro_slots, "appearance": member.appearance,
            "notification_preferences": member.notification_prefs, "joined_at": member.created_at,
        },
        "needs": _rows(Need.objects.filter(member=member).order_by("id"), "capability__slug", "description", "is_active", "created_at"),
        "offers": _rows(Offer.objects.filter(member=member).order_by("id"), "capability__slug", "description", "is_active", "created_at"),
        "skills": _rows(MemberSkill.objects.filter(member=member).order_by("id"), "capability__slug", "level", "proof_url"),
        "traits": _rows(MemberTrait.objects.filter(member=member).order_by("id"), "trait__slug"),
        "consents": _rows(Consent.objects.filter(member=member).order_by("id"), "policy_version", "accepted_at"),
        "work_email_checks": _rows(WorkEmailVerification.objects.filter(member=member), "email_domain", "confirmed_at", "created_at"),
        "posts": _rows(Post.objects.filter(author=member).order_by("id"), "id", "body", "link", "visibility", "status", "created_at"),
        "post_media": _rows(PostMedia.objects.filter(post__author=member).order_by("id"), "post_id", "upload_id", "alt_text", "order"),
        "replies": _rows(Reply.objects.filter(author=member).order_by("id"), "id", "post_id", "parent_id", "body", "status", "created_at"),
        "reactions": _rows(Reaction.objects.filter(member=member).order_by("id"), "post_id", "kind", "created_at"),
        "follows": _rows(Follow.objects.filter(member=member).order_by("id"), "startup_id", "created_at"),
        "startup_interest": _rows(StartupInterest.objects.filter(member=member).order_by("id"), "startup_id", "created_at"),
        "startup_roles": _rows(StartupMember.objects.filter(member=member).order_by("id"), "startup_id", "role", "created_at"),
        "claimed_startups": _rows(Startup.objects.filter(claimed_by=member).order_by("id"), "id", "name", "website_domain", "claimed_at"),
        "jobs_posted": _rows(Job.objects.filter(posted_by=member).order_by("id"), "id", "title", "startup_id", "created_at"),
        "applications": _rows(Application.objects.filter(student=member).order_by("id"), "id", "job_id", "status", "created_at"),
        "connections": [
            {"member_id": c.member_b_id if c.member_a_id == me else c.member_a_id, "created_at": c.created_at}
            for c in Connection.objects.filter(Q(member_a=member) | Q(member_b=member)).order_by("id")
        ],
        "connection_requests_sent": _rows(
            ConnectionRequest.objects.filter(sender=member).order_by("id"), "recipient_id", "note", "status", "created_at"
        ),
        "connection_requests_received": _rows(
            ConnectionRequest.objects.filter(recipient=member).order_by("id"), "sender_id", "status", "created_at"
        ),
        "conversations": conversations,
        "intros_sent": _rows(
            IntroRequest.objects.filter(requester=member).order_by("id"),
            "id", "target_id", "via_id", "message", "status", "outcome_rating", "created_at",
        ),  # fmt: skip
        "intros_received": _rows(IntroRequest.objects.filter(target=member).order_by("id"), "id", "requester_id", "status", "created_at"),
        "intros_brokered": _rows(IntroRequest.objects.filter(via=member).order_by("id"), "id", "requester_id", "target_id", "status"),
        "circuit_legs": legs,
        "notifications": _rows(Notification.objects.filter(member=member).order_by("id"), "kind", "payload", "read_at", "created_at"),
        "reports_filed": _rows(Report.objects.filter(reporter=member).order_by("id"), "target_type", "target_id", "reason", "status", "created_at"),
        "blocks": _rows(Block.objects.filter(blocker=member).order_by("id"), "blocked_id", "created_at"),
        "invite_codes_created": _rows(InviteCode.objects.filter(created_by=member).order_by("id"), "code", "kind", "uses", "max_uses", "created_at"),
        "beta_access": _rows(BetaAccess.objects.filter(member=member), "source", "granted_at", "revoked_at"),
        "daily_drop_history": drops,
        "events": _rows(Event.objects.filter(actor=member).order_by("id"), "type", "target_type", "target_id", "payload", "created_at"),
    }  # fmt: skip


def _build_zip(member: Member) -> bytes:
    storage = get_storage()
    buf = io.BytesIO()
    skipped: list[int] = []
    used = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for upload in MediaUpload.objects.filter(owner=member, status=MediaUpload.Status.READY).order_by("id"):
            try:
                data = storage.get(
                    settings.STORAGE_BUCKETS[upload.purpose], f"{upload.path}/w{settings.MEDIA_VARIANT_WIDTHS[0]}.webp"
                )
            except (FileNotFoundError, OSError):
                skipped.append(upload.pk)
                continue
            if used + len(data) > MAX_MEDIA_BYTES:
                skipped.append(upload.pk)
                continue
            used += len(data)
            z.writestr(f"media/{upload.purpose}-{upload.pk}.webp", data)
        data_json = member_data(member)
        data_json["media_skipped_upload_ids"] = skipped
        z.writestr("data.json", json.dumps(data_json, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False))
        z.writestr("README.txt", README)
    return buf.getvalue()


# -- requesting and reading -----------------------------------------------------------------------------
def latest(member: Member) -> DataExport | None:
    return DataExport.objects.filter(member=member).order_by("-requested_at", "-id").first()


def request_export(member: Member) -> DataExport:
    """Ask for an export. One at a time per member (409 while one is pending or building); 3 a day."""
    if DataExport.objects.filter(member=member, status__in=[DataExport.Status.PENDING, DataExport.Status.BUILDING]).exists():
        raise Conflict("Your export is already being prepared", code="export_in_progress")
    check_rate(member.pk, "export")
    try:
        with transaction.atomic():
            export = DataExport.objects.create(member=member)
    except IntegrityError:  # two requests at the same moment: the database allows one open export
        raise Conflict("Your export is already being prepared", code="export_in_progress") from None
    record("export.requested", actor=member, target_type="export", target_id=export.pk)
    return export


def make_token(export: DataExport) -> str:
    return signing.dumps({"e": export.pk, "m": export.member_id}, salt=SALT)


def download(member: Member, token: str) -> dict:
    """Trade the emailed link for a short storage URL. Someone else's link is a 404; an old one is 410 `export_expired`."""
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.EXPORT_LINK_HOURS * 3600)
        export_id, owner_id = data["e"], data["m"]
    except signing.SignatureExpired:
        raise ApiError(410, "export_expired", "This download link has expired. Request a new export.") from None
    except (signing.BadSignature, KeyError, TypeError):
        raise NotFound() from None
    export = DataExport.objects.filter(pk=export_id, member=member).first()
    if owner_id != member.pk or export is None:
        raise NotFound()
    if export.status != DataExport.Status.READY or export.expires_at is None or export.expires_at <= timezone.now():
        raise ApiError(410, "export_expired", "This download link has expired. Request a new export.")
    url = get_storage().signed_urls(
        settings.STORAGE_BUCKETS["export"], [export.path], expires_in=settings.EXPORT_DOWNLOAD_SECONDS
    )
    record("export.downloaded", actor=member, target_type="export", target_id=export.pk)
    return {"url": url[export.path], "expires_in": settings.EXPORT_DOWNLOAD_SECONDS, "size_bytes": export.size_bytes}


# -- the job --------------------------------------------------------------------------------------------
def _email_link(member: Member, export: DataExport) -> None:
    if not member.email:
        return
    link = f"{settings.APP_URL.rstrip('/')}/settings/export?token={make_token(export)}"
    outbox.queue_email(
        member.email,
        "export.ready",
        "Your Circuit data export is ready",
        f"Your data export is ready. Open this link while signed in to download it:\n{link}\n\n"
        f"The link works for {settings.EXPORT_LINK_HOURS} hours. If you did not ask for this, change your sign-in method "
        "and write to us.\n",
        member=member,
    )


def build_one(export_id: int) -> str:
    """Build one export. Returns the new status. Safe to run twice: a row lock and the status stop a double build."""
    with transaction.atomic():
        export = (
            DataExport.objects.select_for_update(skip_locked=True)
            .select_related("member")
            .filter(pk=export_id, status=DataExport.Status.PENDING)
            .first()
        )
        if export is None:
            return "skipped"
        export.status, export.attempts = DataExport.Status.BUILDING, export.attempts + 1
        export.save(update_fields=["status", "attempts"])
    member = export.member
    try:
        blob = _build_zip(member)
        path = f"exports/{member.pk}/{uuid4().hex}.zip"
        get_storage().put(settings.STORAGE_BUCKETS["export"], path, blob, "application/zip")
    except Exception as exc:
        failed = export.attempts >= MAX_ATTEMPTS
        export.status = DataExport.Status.FAILED if failed else DataExport.Status.PENDING
        export.save(update_fields=["status"])
        log.warning("export_failed", export_id=export.pk, attempts=export.attempts, error=type(exc).__name__)
        if failed:
            record("export.failed", actor=member, target_type="export", target_id=export.pk)
        return export.status
    now = timezone.now()
    export.status, export.path, export.size_bytes = DataExport.Status.READY, path, len(blob)
    export.ready_at, export.expires_at = now, now + timedelta(hours=settings.EXPORT_LINK_HOURS)
    export.save(update_fields=["status", "path", "size_bytes", "ready_at", "expires_at"])
    record("export.ready", actor=member, target_type="export", target_id=export.pk, size_bytes=len(blob))
    _email_link(member, export)
    return export.status


def build_pending(limit: int = 10) -> dict[str, int]:
    """The `build_exports` job."""
    ids = list(DataExport.objects.filter(status=DataExport.Status.PENDING).order_by("id").values_list("pk", flat=True)[:limit])
    counts = {"ready": 0, "retry": 0, "failed": 0, "skipped": 0}
    for pk in ids:
        status = build_one(pk)
        counts[{"ready": "ready", "pending": "retry", "failed": "failed"}.get(status, "skipped")] += 1
    return counts


def expire_old() -> int:
    """Delete the files of exports past their link lifetime and mark them expired. Used by the retention job."""
    due = list(DataExport.objects.filter(status=DataExport.Status.READY, expires_at__lte=timezone.now()))
    if due:
        get_storage().delete(settings.STORAGE_BUCKETS["export"], [e.path for e in due if e.path])
        DataExport.objects.filter(pk__in=[e.pk for e in due]).update(status=DataExport.Status.EXPIRED, path="")
    return len(due)
