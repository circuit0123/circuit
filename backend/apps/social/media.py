"""Images for build logs and chat. The browser uploads straight to a signed storage URL; `complete` then checks the file.

Checks: real image type (JPEG, PNG, WebP by content, not by name or header), size, pixel count. The stored files are
fresh re-encodes, so EXIF (including GPS location) never survives. Two sizes are kept (1440 and 480 wide), the original
is deleted. This is the one heavy step done inside a request: one image of at most 5 MB, bounded on purpose.
"""

import io
import uuid
from collections.abc import Collection, Iterable

import structlog
from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.accounts.models import Member, Role
from apps.events.services import record
from apps.social.models import MediaUpload
from apps.social.relations import MESSAGING_ROLES, SOCIAL_ROLES
from core.cache import get_cache
from core.errors import ApiError, Forbidden, NotFound
from core.ratelimit import check_rate
from core.storage import get_storage

log = structlog.get_logger("media")
CONTENT_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
URL_TTL = 3000  # cached signed URLs live 50 min; the signed URLs themselves last 60
VARIANTS = {w: f"w{w}.webp" for w in settings.MEDIA_VARIANT_WIDTHS}


PICTURE_PURPOSES = {MediaUpload.Purpose.AVATAR, MediaUpload.Purpose.STARTUP_LOGO}


def bucket(purpose: str) -> str:
    return settings.STORAGE_BUCKETS[purpose]


def widths(purpose: str) -> tuple[int, ...]:
    return settings.MEDIA_AVATAR_WIDTHS if purpose in PICTURE_PURPOSES else settings.MEDIA_VARIANT_WIDTHS


def create_upload(member: Member, purpose: str, content_type: str, size: int) -> tuple[MediaUpload, str]:
    allowed: Collection[str] = MESSAGING_ROLES  # messages and avatars: every member who can use the app
    if purpose == MediaUpload.Purpose.POST:
        allowed = SOCIAL_ROLES
    elif purpose == MediaUpload.Purpose.STARTUP_LOGO:
        allowed = {Role.FOUNDER}
    if member.role not in allowed:
        raise Forbidden()
    if content_type not in CONTENT_TYPES:
        raise ApiError(422, "unsupported_image", "Use a JPEG, PNG or WebP image")
    if size > settings.MAX_UPLOAD_BYTES:
        raise ApiError(422, "image_too_large", "Images can be up to 5 MB")
    check_rate(member.pk, "upload")
    path = f"{purpose}/{member.pk}/{uuid.uuid4().hex}"
    url = get_storage().signed_upload_url(bucket(purpose), f"{path}/original")
    upload = MediaUpload.objects.create(owner=member, purpose=purpose, path=path)
    return upload, url


def _encode(img: Image.Image, max_bytes: int) -> bytes:
    """WebP at MEDIA_WEBP_QUALITY; if that is still bigger than the size budget for this width (storage is 1 GB on the free plan),
    try lower qualities until it fits. A photo of a whiteboard stays sharp, a noisy 12-megapixel photo shrinks more."""
    blob = b""
    for quality in (settings.MEDIA_WEBP_QUALITY, 70, 60, 50):
        if quality > settings.MEDIA_WEBP_QUALITY:
            continue
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=quality, method=4)  # no exif= argument: metadata is dropped
        blob = buf.getvalue()
        if len(blob) <= max_bytes:
            break
    return blob


def _process(data: bytes, sizes: tuple[int, ...] | None = None) -> tuple[dict[int, bytes], tuple[int, int]]:
    Image.MAX_IMAGE_PIXELS = settings.MEDIA_MAX_PIXELS
    try:
        probe = Image.open(io.BytesIO(data))
        if probe.format not in CONTENT_TYPES.values():
            raise ApiError(422, "unsupported_image", "Use a JPEG, PNG or WebP image")
        probe.verify()  # catches truncated and corrupt files; the image must be reopened after
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as e:
        raise ApiError(422, "invalid_image", "This file is not a usable image") from e
    img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    out: dict[int, bytes] = {}
    for width in sizes or settings.MEDIA_VARIANT_WIDTHS:
        v = img if img.width <= width else img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)
        out[width] = _encode(v, settings.MEDIA_VARIANT_MAX_BYTES[width])
    return out, (img.width, img.height)


def complete_upload(member: Member, upload_id: int) -> MediaUpload:
    upload = MediaUpload.objects.filter(pk=upload_id, owner=member).first()
    if upload is None:
        raise NotFound()
    if upload.status == MediaUpload.Status.READY:
        return upload  # idempotent
    store, b = get_storage(), bucket(upload.purpose)
    try:
        data = store.get(b, f"{upload.path}/original")
    except FileNotFoundError:
        raise ApiError(409, "upload_missing", "The file has not arrived yet. Upload it to the signed URL first.") from None
    try:
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise ApiError(422, "image_too_large", "Images can be up to 5 MB")
        variants, (w, h) = _process(data, widths(upload.purpose))
    except ApiError:
        store.delete(b, [f"{upload.path}/original"])  # never keep a file we refused
        raise
    for width, blob in variants.items():
        store.put(b, f"{upload.path}/{VARIANTS[width]}", blob, "image/webp")
    store.delete(b, [f"{upload.path}/original"])
    upload.status, upload.width, upload.height = MediaUpload.Status.READY, w, h
    upload.save(update_fields=["status", "width", "height"])
    record("media.uploaded", actor=member, target_type="media_upload", target_id=upload.pk, purpose=upload.purpose)
    return upload


def claim_uploads(member: Member, ids: list[int], purpose: str) -> list[MediaUpload]:
    """The member's own, finished, not-yet-attached uploads, in the order given. Anything else is a 404 (IDOR)."""
    if len(set(ids)) != len(ids):
        raise ApiError(422, "duplicate_media", "The same image was listed twice")
    found = {
        u.pk: u
        for u in MediaUpload.objects.filter(
            pk__in=ids,
            owner=member,
            purpose=purpose,
            status=MediaUpload.Status.READY,
            post_media__isnull=True,
            message__isnull=True,
            highlight__isnull=True,
        )
    }
    if len(found) != len(ids):
        raise NotFound("One of the images was not found")
    return [found[i] for i in ids]


def urls_for(uploads: Iterable[MediaUpload]) -> dict[int, dict]:
    """{upload id: {"w1440": url, "w480": url, "width", "height"}}. One storage call per bucket for the uncached paths."""
    uploads = list(uploads)
    cache, store = get_cache(), get_storage()
    result: dict[int, dict] = {}
    missing: dict[str, list[str]] = {}
    for u in uploads:
        entry = {"width": u.width, "height": u.height}
        for width in widths(u.purpose):
            name = VARIANTS[width]
            path = f"{u.path}/{name}"
            cached = cache.get_json(f"media:{path}")
            if cached:
                entry[f"w{width}"] = cached
            else:
                missing.setdefault(bucket(u.purpose), []).append(path)
        result[u.pk] = entry
    signed: dict[str, str] = {}
    for b, paths in missing.items():
        for path, url in store.signed_urls(b, paths).items():
            signed[path] = url
            cache.set_json(f"media:{path}", url, URL_TTL)
    for u in uploads:
        for width in widths(u.purpose):
            name = VARIANTS[width]
            result[u.pk].setdefault(f"w{width}", signed.get(f"{u.path}/{name}", ""))
    return result


def delete_files(uploads: Iterable[MediaUpload]) -> None:
    by_bucket: dict[str, list[str]] = {}
    for u in uploads:
        by_bucket.setdefault(bucket(u.purpose), []).extend(f"{u.path}/{n}" for n in VARIANTS.values())
    for b, paths in by_bucket.items():
        try:
            get_storage().delete(b, paths)
        except Exception:  # best effort: the rows are already gone, an orphan file is harmless and private
            log.warning("media_delete_failed", bucket=b)


# -- profile photos and startup logos ---------------------------------------------------------------------
# One small signed URL per picture. `person()` and `author()` ask `photo_of(member)`; a list endpoint calls `prime_photos(members)`
# first so the whole list is signed in one storage call. Without priming a single lookup still works (cached, then one call).
def small_urls(folders: Iterable[str]) -> dict[str, str]:
    """{folder: signed w480 URL} for pictures in the avatars bucket. One storage call per bucket for the uncached ones."""
    cache, store = get_cache(), get_storage()
    name = VARIANTS[settings.MEDIA_AVATAR_WIDTHS[0]]
    found: dict[str, str] = {}
    missing: dict[str, list[str]] = {}
    for folder in {f for f in folders if f}:
        cached = cache.get_json(f"media:{folder}/{name}")
        if cached:
            found[folder] = cached
        else:
            missing.setdefault(bucket(folder.split("/", 1)[0]), []).append(folder)
    for b, group in missing.items():
        signed = store.signed_urls(b, [f"{f}/{name}" for f in group])
        for folder in group:
            url = signed.get(f"{folder}/{name}", "")
            if url:
                found[folder] = url
                cache.set_json(f"media:{folder}/{name}", url, URL_TTL)
    return found


def prime_photos(members: Iterable[Member]) -> None:
    """Sign every listed member's photo in one go. Under-18 members' photos are shown to nobody but themselves (`own_photo`)."""
    members = [m for m in members if m is not None]
    urls = small_urls(m.photo_path for m in members if m.photo_path and not m.is_minor)
    for m in members:
        m._photo_url = urls.get(m.photo_path) if m.photo_path and not m.is_minor else None  # type: ignore[attr-defined]


def photo_of(member: Member) -> str | None:
    if not hasattr(member, "_photo_url"):
        prime_photos([member])
    return member._photo_url  # type: ignore[attr-defined]


def own_photo(member: Member) -> str | None:
    """The member's own photo, also for an under-18 member (it is never shown to anyone else)."""
    return small_urls([member.photo_path]).get(member.photo_path) if member.photo_path else None


def prime_logos(startups: Iterable) -> None:
    startups = list(startups)
    urls = small_urls(s.logo_path for s in startups if s.logo_path)
    for s in startups:
        s._logo_url = urls.get(s.logo_path) if s.logo_path else None


def logo_of(startup) -> str | None:
    if not hasattr(startup, "_logo_url"):
        prime_logos([startup])
    return startup._logo_url


def set_picture(member: Member, upload_id: int, purpose: str, old_folder: str) -> str:
    """Take one of the member's finished uploads as a photo or logo and drop the previous picture. Returns the new folder."""
    upload = claim_uploads(member, [upload_id], purpose)[0]
    if old_folder and old_folder != upload.path:
        delete_picture(old_folder)
    return upload.path


def delete_picture(folder: str) -> None:
    """Remove a picture's files and its upload row (best effort on the files)."""
    old = MediaUpload.objects.filter(path=folder).first()
    if old is not None:
        delete_files([old])
        old.delete()
