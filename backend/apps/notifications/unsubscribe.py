"""One-click unsubscribe links for notification emails.

The token is signed by Django's `signing` (tamper-proof, carries its own timestamp) and holds only the member id and the
notification type. It works without signing in, expires after UNSUBSCRIBE_TOKEN_DAYS, and can only ever do one thing:
turn off the email channel of that one type. Opening it changes nothing; only a POST does (so mail scanners that
prefetch links cannot unsubscribe anyone).
"""

from django.conf import settings
from django.core import signing

from apps.notifications import prefs

SALT = "circuit.unsubscribe.v1"


def make_token(member_id: int, type_: str) -> str:
    return signing.dumps({"m": member_id, "t": type_}, salt=SALT, compress=True)


def read_token(token: str) -> tuple[int, str] | None:
    """(member id, type) if the token is genuine and fresh, else None. Never raises for bad input."""
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.UNSUBSCRIBE_TOKEN_DAYS * 86400)
        member_id, type_ = data["m"], data["t"]
    except (signing.BadSignature, KeyError, TypeError):
        return None
    if not isinstance(member_id, int) or type_ not in prefs.TYPES:
        return None
    return member_id, type_


def headers_for(token: str) -> dict[str, str]:
    """List-Unsubscribe headers (RFC 2369 and RFC 8058 one-click) pointing at the API, which answers the POST."""
    url = f"{settings.API_URL.rstrip('/')}/api/unsubscribe?token={token}"
    return {"List-Unsubscribe": f"<{url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def page_url(token: str) -> str:
    return f"{settings.APP_URL.rstrip('/')}/unsubscribe?token={token}"
