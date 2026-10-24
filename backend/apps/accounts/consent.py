"""Consent records: which version of the privacy policy and terms a member accepted, and when (DPDP).

The version is a setting (POLICY_VERSION), so the text can change without code changes: bump the setting and everyone is asked
again. The gate that turns a missing or old consent into 403 `consent_required` is core/gate.py.
"""

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Consent, Member
from apps.events.services import record
from core.errors import ApiError


def latest(member: Member) -> Consent | None:
    return Consent.objects.filter(member=member).order_by("-accepted_at", "-id").first()


def accept(member: Member, policy_version: str) -> Consent:
    """Record that the member accepted the CURRENT version. Accepting an old or made-up version is a 422. Safe to repeat."""
    if policy_version != settings.POLICY_VERSION:
        raise ApiError(422, "policy_version_mismatch", "That is not the current policy version. Reload and try again.")
    existing = Consent.objects.filter(member=member, policy_version=policy_version).order_by("accepted_at").first()
    if existing:
        return existing
    consent = Consent.objects.create(member=member, policy_version=policy_version, accepted_at=timezone.now())
    record("consent.accepted", actor=member, target_type="member", target_id=member.pk, policy_version=policy_version)
    return consent
