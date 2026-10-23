"""Tell the other member's open app that a message arrived (Supabase Realtime, private Broadcast).

Only ids travel over the channel ({message_id, conversation_id}); the client then fetches the message through our API,
so permissions are checked there. Failure is fine: the message is already saved and the client refetches on reconnect.
"""

import time
from collections.abc import Callable

import httpx
import structlog
from django.conf import settings

log = structlog.get_logger("realtime")
Sender = Callable[[str, str, dict], None]
_sender: Sender | None = None


def topic(conversation_id: int) -> str:
    return f"conversation:{conversation_id}"


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
    global _sender
    _sender = sender


def broadcast(conversation_id: int, message_id: int) -> None:
    try:
        (_sender or _supabase_send)(
            topic(conversation_id), "message", {"message_id": message_id, "conversation_id": conversation_id}
        )
    except Exception:  # never let a chat nudge break the request that already saved the message
        log.warning("realtime_broadcast_failed", topic=topic(conversation_id))
