"""What each notification says, in one place: the one-line text in the app and the subject of the email.

Written at read/send time from the kind and the actor's current name, so a name is never stored in the notification
(payloads hold ids only) and a deleted member shows as "Deleted member". Voice: plain, warm, specific (DESIGN.md §9).
"""

from apps.notifications import prefs

# kind -> (one-line text, email subject, where it opens in the app). {who} is the actor's name, or "Someone".
COPY: dict[str, tuple[str, str, str]] = {
    "intro.received": ("{who} would like to meet you.", "{who} would like to meet you", "/intros"),
    "intro.broker_request": ("{who} asked you to vouch for an introduction.", "Can you vouch for an introduction?", "/intros"),
    "intro.vouched": ("{who} vouched for your introduction request.", "Your introduction request moved forward", "/intros"),
    "intro.accepted": ("{who} accepted your introduction.", "Your introduction was accepted", "/intros"),
    "intro.declined": ("Your introduction request was declined.", "An update on your introduction request", "/intros"),
    "intro.expired": ("Your introduction request expired without an answer.", "Your introduction request expired", "/intros"),
    "application.received": ("{who} applied to one of your roles.", "A new application for your role", "/jobs/applicants"),
    "application.status": ("Your application has a new status.", "An update on your application", "/jobs/applications"),
    "circuit.proposed": ("A new circuit is waiting for your answer.", "A circuit is waiting for your answer", "/circuits"),
    "circuit.activated": ("Everyone said yes. Your circuit is on.", "Your circuit is on", "/circuits"),
    "circuit.declined": ("Your circuit ended because someone said no.", "Your circuit did not go ahead", "/circuits"),
    "circuit.expired": ("Your circuit expired before everyone answered.", "Your circuit expired", "/circuits"),
    "circuit.leg_done": ("{who} marked their part of your circuit as done.", "Your circuit moved forward", "/circuits"),
    "circuit.completed": ("Circuit closed. Everyone did their part.", "Your circuit closed", "/circuits"),
    "message.new": ("{who} sent you a message.", "{who} sent you a message", "/inbox"),
    "post.reply": ("{who} replied to your build log.", "{who} replied to your build log", "/pulse"),
    "startup.interest": ("Someone showed interest in your startup.", "Someone showed interest in your startup", "/startups"),
    "startup.claimed": ("You claimed your startup.", "You claimed your startup", "/startups"),
    "moderation.warning": (
        "A moderator reviewed something you shared and asked you to follow the community guidelines.",
        "A message from the Circuit moderators",
        "/help/community-guidelines",
    ),
}

# kind -> (target type, payload key) so the app can open the right screen without another call
TARGETS: dict[str, tuple[str, str]] = {
    "intro.": ("intro", "intro_id"),
    "application.": ("application", "application_id"),
    "circuit.": ("circuit", "circuit_id"),
    "message.": ("conversation", "conversation_id"),
    "post.reply": ("post", "post_id"),
    "startup.": ("startup", "startup_id"),
}

TYPE_LABELS = {
    "intros": "introductions",
    "applications": "applications",
    "circuits": "circuits",
    "messages": "messages",
    "pulse_replies": "replies to your build logs",
    "announcements": "announcements from your organisation",
}


def text(kind: str, who: str | None) -> str:
    template = COPY.get(kind, ("You have a new notification.", "", ""))[0]
    return template.format(who=who or "Someone")


def target(kind: str, payload: dict) -> dict | None:
    for prefix, (type_, key) in TARGETS.items():
        if kind.startswith(prefix) and isinstance(payload.get(key), int):
            return {"type": type_, "id": payload[key]}
    return None


def email_parts(kind: str, who: str | None) -> tuple[str, str, str] | None:
    """(subject, one-line body, app path) for a kind that can be emailed, else None."""
    entry = COPY.get(kind)
    if entry is None or prefs.type_for(kind) is None:
        return None  # account notices are in-app only
    line, subject, path = entry
    name = who or "Someone"
    return subject.format(who=name), line.format(who=name), path
