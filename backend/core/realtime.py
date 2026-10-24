"""Tell a member's open app that something changed (Supabase Realtime, private Broadcast).

Only ids travel over the channel; the client then fetches the data through our API, so permissions are checked there.
Failure is fine: the data is already saved and the client refetches on reconnect (PRODUCTION.md §14 row 14).
Who may listen to which topic is decided by the policies in core/realtime_sql.py and messaging/0003.

    member:<id>        notifications ({notification_id})
    circuit:<id>       circuit live status ({circuit_id})
    conversation:<id>  chat messages ({message_id, conversation_id})
"""

import time
from collections.abc import Callable

import httpx
import structlog
from django.conf import settings

log = structlog.get_logger("realtime")
Sender = Callable[[str, str, dict], None]
_sender: Sender | None = None


def _supabase_send(topic_name: str, event: str, payload: dict) -> None:
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        return  # dev without Supabase: clients poll
    body = {"messages": [{"topic": topic_name, "event": event, "payload": payload, "private": True}]}
    headers = {"apikey": settings.SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"}
    for attempt in range(2):
        try:
            r = httpx.post(
                f"{settings.SUPABASE_URL.rstrip('/')}/realtime/v1/api/broadcast", json=body, headers=headers, timeout=3.0
            )
            if r.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2 * 2**attempt)
    log.warning("realtime_broadcast_failed", topic=topic_name)


def set_sender(sender: Sender | None) -> None:
    """Tests install a recorder here; None restores the real Supabase sender."""
    global _sender
    _sender = sender


def send(topic_name: str, event: str, payload: dict) -> None:
    """Broadcast one event. Never raises: a failed nudge must not break the request that already saved the data."""
    try:
        (_sender or _supabase_send)(topic_name, event, payload)
    except Exception:
        log.warning("realtime_broadcast_failed", topic=topic_name)
