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

# Richer in-app lines for when we know the other people and things involved (looked up when the list is read, in a few bulk
# queries; ids only are stored). Used only when every {placeholder} could be filled, else the plain COPY line above is shown.
# Email subjects stay on the plain lines on purpose: an email can sit in an inbox for years.
RICH: dict[str, str] = {
    "intro.accepted": "{who} accepted your intro request to {target}.",
    "intro.accepted.broker": "{who} accepted the intro request from {requester} that you vouched for.",
    "intro.vouched": "{who} vouched for your intro request to {target}.",
    "intro.broker_request": "{who} asked you to vouch for an intro to {target}.",
    "intro.received": "{who} would like to meet you, vouched for by {via}.",
    "application.received": "{who} applied for {job}.",
    "application.status.shortlisted": "You were shortlisted for {job}.",
    "application.status.hired": "You got the {job} role.",
    "application.status.rejected": "Your application for {job} was not selected.",
    "circuit.leg_done": "{who} marked their help with {capability} as done.",
    "startup.interest": "Someone showed interest in {startup}.",
    "startup.claimed": "You claimed {startup}.",
}

TYPE_LABELS = {
    "intros": "introductions",
    "applications": "applications",
    "circuits": "circuits",
    "messages": "messages",
    "pulse_replies": "replies to your build logs",
    "announcements": "announcements from your organisation",
}


def text(kind: str, who: str | None, extra: dict | None = None, variant: str | None = None) -> str:
    """The line to show. `extra` holds the other names and things ({target}, {job}...); `variant` picks a RICH line for the same kind."""
    values = {"who": who or "Someone", **(extra or {})}
    rich = RICH.get(variant or kind)
    if rich is not None:
        try:
            return rich.format(**values)
        except KeyError:  # something could not be looked up (deleted, hidden): say the plain thing instead
            pass
    template = COPY.get(kind, ("You have a new notification.", "", ""))[0]
    return template.format(who=values["who"])


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
