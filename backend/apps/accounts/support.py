"""Questions, corrections, data requests and grievances (DPDP). One endpoint, one email to the right inbox.

The message goes to SUPPORT_EMAIL (grievances to the grievance officer's address) with the member's id and a Reply-To, and the
member gets a short acknowledgement with a reference. Nothing from the message is logged or recorded as an event (ids and kind only).
"""

from django.conf import settings

from apps.accounts.models import Member
from apps.events.services import record
from core import email as outbox
from core.ratelimit import check_rate

KINDS = ("question", "correction", "data_request", "grievance")


def contact_for(kind: str) -> str:
    return settings.GRIEVANCE["email"] if kind == "grievance" else settings.SUPPORT_EMAIL


def submit(member: Member, kind: str, message: str) -> str:
    """Queue the email and return the reference shown to the member. Rate limited (5 a day)."""
    check_rate(member.pk, "support")
    headers = {"Reply-To": member.email} if member.email else {}
    row = outbox.queue_email(
        contact_for(kind),
        f"support.{kind}",
        f"[{kind}] from member {member.pk}",
        f"Member id: {member.pk}\nKind: {kind}\n\n{message.strip()}\n",
        headers=headers,
        member=member,
    )
    reference = f"S-{row.pk}"
    if member.email:
        outbox.queue_email(
            member.email,
            "support.ack",
            f"We received your message ({reference})",
            f"Thanks for writing to Circuit. Your reference is {reference}. We will reply to this address.\n"
            + (
                f"Grievance officer: {settings.GRIEVANCE['name']}, {settings.GRIEVANCE['email']}\n" if kind == "grievance" else ""
            ),
            member=member,
        )
    record("support.requested", actor=member, target_type="support", target_id=row.pk, kind=kind)
    return reference
