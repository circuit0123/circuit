"""The landing site is a different origin from the app, and the app's CORS list is exact (APP_URL only). The waitlist form is
the one thing the landing site may call, so this lets LANDING_URL through for that one path and for nothing else."""

from urllib.parse import urlsplit

from django.conf import settings

WAITLIST_PATH = "/api/waitlist"


def landing_origin() -> str:
    parts = urlsplit(settings.LANDING_URL)
    return f"{parts.scheme}://{parts.netloc}"


def allow_landing_for_waitlist(sender, request, **kwargs) -> bool:
    return request.path_info == WAITLIST_PATH and request.headers.get("origin", "") == landing_origin()
