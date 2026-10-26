"""Highlights: up to six projects pinned to a profile (DESIGN.md §4 "Profile"). The picture is one of the member's own `highlight`
uploads (social/media.py). They are drawn inside `ProfileOut`, so they are exactly as visible as the profile itself, with one more
rule: an under-18 member's highlights are shown to nobody but themselves, like their photo.
"""

from django.db import transaction

from apps.accounts.models import Member
from apps.events.services import record
from apps.social import media
from apps.social.models import Highlight, MediaUpload
from core.errors import ApiError

MAX_HIGHLIGHTS = 6


def rows_for(viewer: Member, target: Member) -> list[dict]:
    if target.is_minor and viewer.pk != target.pk:
        return []
    items = list(Highlight.objects.filter(member=target).select_related("upload"))
    urls = media.urls_for(h.upload for h in items)
    return [
        {"id": h.pk, "title": h.title, "link": h.link, "image": {"alt_text": h.alt_text, **urls[h.upload_id]}} for h in items
    ]


def replace(member: Member, items: list[dict]) -> list[dict]:
    """Make my highlights exactly `items`, in order. Each item names one of my finished `highlight` uploads: either a new one, or
    one already pinned (so re-sending the list keeps it). Someone else's upload, or one used elsewhere, is a 404. Uploads that
    drop out of the list are deleted with their files."""
    if len(items) > MAX_HIGHLIGHTS:
        raise ApiError(422, "too_many_highlights", f"Pin up to {MAX_HIGHLIGHTS} projects")
    ids = [i["upload_id"] for i in items]
    if len(set(ids)) != len(ids):
        raise ApiError(422, "duplicate_media", "The same image was listed twice")
    with transaction.atomic():
        pinned = {h.upload_id: h for h in Highlight.objects.select_for_update().filter(member=member)}
        fresh = media.claim_uploads(member, [i for i in ids if i not in pinned], MediaUpload.Purpose.HIGHLIGHT)
        uploads = {u.pk: u for u in fresh} | {pk: h.upload for pk, h in pinned.items()}
        dropped = [h.upload for pk, h in pinned.items() if pk not in ids]
        Highlight.objects.filter(member=member).delete()  # rows only; the pictures of kept ones stay
        Highlight.objects.bulk_create(
            Highlight(
                member=member, upload=uploads[i["upload_id"]], title=i["title"].strip(), link=i["link"],
                alt_text=i["alt_text"].strip(), position=n,
            )
            for n, i in enumerate(items)
        )  # fmt: skip
        record("member.highlights_set", actor=member, target_type="member", target_id=member.pk, count=len(items))
    for upload in dropped:
        media.delete_picture(upload.path)
    return rows_for(member, member)
