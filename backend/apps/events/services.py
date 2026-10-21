"""Append-only product events. One function so every action is recorded the same way."""

from apps.events.models import Event

# Payloads are pseudonymous: ids and enums only, never names, emails or free text.


def record(type: str, *, actor=None, target_type: str = "", target_id: int | None = None, **payload) -> Event:
    return Event.objects.create(
        actor_id=getattr(actor, "pk", actor), type=type, target_type=target_type, target_id=target_id, payload=payload
    )
