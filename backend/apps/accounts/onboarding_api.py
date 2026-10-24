"""Onboarding state endpoints (DESIGN.md §4 "Sign-up and onboarding"). Under /api/onboarding/, so they stay open while the
invite-only beta is on: the invite screen is itself one of the steps."""

from typing import Any, Literal

from ninja import Router, Schema
from pydantic import ConfigDict, Field, StrictBool

from apps.accounts import onboarding_state
from core import gate
from core.auth import current_context, current_member
from core.ratelimit import check_rate
from core.schemas import SRC_MAX, SRC_PATTERN

router = Router()
Step = Literal[
    "invite", "name", "role", "age", "safety", "where", "work", "offers", "needs", "organisation", "photo", "colour", "ready",
    "focus", "stage", "cheque", "verify", "org_kind", "org", "org_verify", "goal",
]  # fmt: skip


class OnboardingOut(Schema):
    branch: Literal["default", "investor", "partner"]  # from the Role answer; decides which screens follow
    steps: list[str]  # the screens for this branch, in order
    skip: list[str]  # screens to skip because we already know the answer (a name, a city, an organisation, no invite needed)
    current_step: str | None
    completed_at: str | None
    answers: dict[str, Any]  # what they said at each step, so screens can be pre-filled
    signup_source: str


class OnboardingPatch(Schema):
    model_config = ConfigDict(extra="forbid")
    current_step: Step | None = None
    answers: dict[Step, dict[str, Any]] | None = None
    signup_source: str | None = Field(None, max_length=SRC_MAX, pattern=SRC_PATTERN)
    completed: StrictBool | None = None


@router.get(
    "/onboarding/state",
    response=OnboardingOut,
    summary="Onboarding progress",
    description="Where this member is in sign-up, what they answered, and which screens to show, skip or reorder, in one call. "
    "Open while the beta gate is on.",
)
def get_state(request):
    return onboarding_state.state(current_member(request), gate.passes(current_context(request)))


@router.patch(
    "/onboarding/state",
    response=OnboardingOut,
    summary="Save an onboarding step",
    description="Saves the current step and merges answers per step (each answer at most 2,000 characters). `signup_source` is "
    "kept from the first call that sends one; later values are ignored. `completed: true` marks onboarding finished. "
    "Unknown steps or fields are 422. Rate limited.",
)
def patch_state(request, body: OnboardingPatch):
    member = current_member(request)
    check_rate(member.pk, "onboarding_state")
    return onboarding_state.save(member, gate.passes(current_context(request)), body.dict(exclude_unset=True))
