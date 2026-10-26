"""Tell the other member's open app that a message arrived (Supabase Realtime, private Broadcast).

Only ids travel over the channel ({message_id, conversation_id}); the client then fetches the message through our API,
so permissions are checked there. Failure is fine: the message is already saved and the client refetches on reconnect.
The sender itself is shared with notifications and circuits: core/realtime.py.
"""

from core import realtime as _core
from core.realtime import _supabase_send, httpx, send, set_sender  # noqa: F401  (re-exported: tests and callers use this module)


def topic(conversation_id: int) -> str:
    return f"conversation:{conversation_id}"


def broadcast(conversation_id: int, message_id: int) -> None:
    _core.send(topic(conversation_id), "message", {"message_id": message_id, "conversation_id": conversation_id})


def conversation_changed(member_id: int, conversation_id: int) -> None:
    """A conversation this member has not listed yet (a new request) or one of theirs that changed state (accepted):
    nudge their member channel so the Inbox refetches. Ids only; the same private channel notifications use."""
    _core.send(f"member:{member_id}", "conversation", {"conversation_id": conversation_id})
