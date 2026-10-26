"""A member's profile photo. The picture itself goes through the same upload flow as every image (social/media.py)."""

from apps.accounts.models import Member
from apps.events.services import record
from apps.social import media
from apps.social.models import MediaUpload


def set_photo(member: Member, upload_id: int) -> Member:
    """Use one of my finished `avatar` uploads as my photo. The previous photo is deleted."""
    member.photo_path = media.set_picture(member, upload_id, MediaUpload.Purpose.AVATAR, member.photo_path)
    member.save(update_fields=["photo_path", "updated_at"])
    record("member.photo_set", actor=member, target_type="member", target_id=member.pk)
    return member


def remove_photo(member: Member) -> Member:
    if member.photo_path:
        media.delete_picture(member.photo_path)
        member.photo_path = ""
        member.save(update_fields=["photo_path", "updated_at"])
        record("member.photo_removed", actor=member, target_type="member", target_id=member.pk)
    return member
