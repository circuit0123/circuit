"""Resumable onboarding (F1, DESIGN.md §4 "Sign-up and onboarding"): the app saves each step so closing it resumes in place.

State lives on the member: `onboarding` = {current_step, completed_at, answers: {step: {...}}}, and `signup_source`
(which landing page or invite brought them; the first one sticks). Nothing here is asked that we can already infer.
"""

import json
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Member
from apps.events.services import record
from core.errors import ApiError

# Screen keys, in DESIGN.md order. Steps 1-2 (sign-in) happen before a member exists; step 3 is the invite screen.
DEFAULT_STEPS = (
    "invite",
    "name",
    "role",
    "age",
    "safety",
    "where",
    "work",
    "offers",
    "needs",
    "organisation",
    "photo",
    "colour",
    "ready",
)
INVESTOR_STEPS = ("invite", "name", "role", "age", "where", "focus", "stage", "cheque", "verify", "photo", "colour", "ready")
PARTNER_STEPS = ("invite", "name", "role", "age", "where", "org_kind", "org", "org_verify", "goal", "photo", "colour", "ready")
ALL_STEPS = tuple(dict.fromkeys(DEFAULT_STEPS + INVESTOR_STEPS + PARTNER_STEPS))
MAX_ANSWER_BYTES = 2000


def branch(member: Member, answers: dict) -> str:
    choice = (answers.get("role") or {}).get("choice")
    if member.role == "investor" or choice == "invest":
        return "investor"
    if choice == "partner":
        return "partner"
    return "default"


def state(member: Member, beta_access: bool) -> dict:
    """The whole onboarding picture in one call: where they are, what they said, which screens to show or skip."""
    saved = member.onboarding or {}
    answers = saved.get("answers", {})
    which = branch(member, answers)
    steps = {"default": DEFAULT_STEPS, "investor": INVESTOR_STEPS, "partner": PARTNER_STEPS}[which]
    needs_invite = settings.BETA_MODE and not beta_access
    skip = []
    if not needs_invite:
        skip.append("invite")
    if member.display_name:
        skip.append("name")
    if member.city or member.location:
        skip.append("where")
    if member.organisation_id:
        skip += ["organisation", "org"]  # student/partner organisation steps: found from the verified email domain or an invite
    if not member.is_minor:
        skip.append("safety")  # the under-18 safety screen only shows to under-18s
    return {
        "branch": which,
        "steps": list(steps),
        "skip": [s for s in steps if s in skip],
        "current_step": saved.get("current_step"),
        "completed_at": saved.get("completed_at"),
        "answers": answers,
        "signup_source": member.signup_source,
    }


def save(member: Member, beta_access: bool, patch: dict) -> dict:
    """Merge a step into the saved state. `answers` merge per step; `signup_source` is set once (first touch wins)."""
    answers_in: dict[str, Any] = patch.get("answers") or {}
    for key, value in answers_in.items():
        if len(json.dumps(value)) > MAX_ANSWER_BYTES:
            raise ApiError(422, "answer_too_large", f"The answer for {key} is too long.")
    with transaction.atomic():
        locked = Member.objects.select_for_update().get(pk=member.pk)
        saved = dict(locked.onboarding or {})
        saved["answers"] = {**saved.get("answers", {}), **answers_in}
        if patch.get("current_step"):
            saved["current_step"] = patch["current_step"]
        if patch.get("completed") and not saved.get("completed_at"):
            saved["completed_at"] = timezone.now().isoformat()
        locked.onboarding = saved
        fields = ["onboarding", "updated_at"]
        if patch.get("signup_source") and not locked.signup_source:
            locked.signup_source = patch["signup_source"]
            fields.append("signup_source")
        locked.save(update_fields=fields)
        # steps only: the answers hold personal text and never go into the events table
        record("onboarding.updated", actor=locked, step=saved.get("current_step"), completed=bool(saved.get("completed_at")))
    return state(locked, beta_access)
