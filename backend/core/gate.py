"""The access gates: consent (Stage 7) and the invite-only beta (F18). Both are called from one place,
SupabaseAuth.authenticate, so every protected endpoint is gated without its author doing anything.

Public endpoints (/api/health*, /api/config, /api/waitlist, /api/support/contact, /api/unsubscribe, /api/demo/*) are `auth=None`
and never reach the gates. Of the protected ones, a few stay open on purpose:

- Consent: a member who has not accepted the current policy version can still ask who they are, accept it, export or delete
  their data, and write to support. Everything else answers 403 `consent_required`.
- Beta: a signed-in member without access can still ask who they are, redeem a code, use the onboarding helpers, accept the
  policy, export or delete their data, and write to support. Everything else answers 403 `beta_required`.

Privacy rights (export, delete, support) never depend on holding an invite or on accepting the latest text.
"""

from django.conf import settings
from django.http import HttpRequest

from core.errors import BetaRequired, ConsentRequired

ME = ("GET", "/api/me")
CONSENT = ("POST", "/api/me/consent")
PRIVACY_RIGHTS = {
    ("GET", "/api/me/export"),
    ("POST", "/api/me/export"),
    ("GET", "/api/me/export/download"),
    ("POST", "/api/me/deletion"),
    ("POST", "/api/support"),
}

CONSENT_EXEMPT = {ME, CONSENT} | PRIVACY_RIGHTS
BETA_EXEMPT_EXACT = {ME, ("POST", "/api/beta/redeem"), CONSENT} | PRIVACY_RIGHTS
BETA_EXEMPT_PREFIXES = ("/api/onboarding/",)


def _key(request: HttpRequest) -> tuple[str, str]:
    return request.method or "", request.path_info


def needs_consent(member) -> bool:
    """True if the member has not accepted the current POLICY_VERSION (no consent row, or only older ones)."""
    from apps.accounts.models import Consent

    return not Consent.objects.filter(member=member, policy_version=settings.POLICY_VERSION).exists()


def passes(ctx) -> bool:
    """True if this caller is let in by the beta right now (always true while BETA_MODE is off). May grant access from the allowlist."""
    from apps.beta import services

    return not settings.BETA_MODE or services.has_access(ctx.member, ctx.verified_email)


def enforce(request: HttpRequest, ctx) -> None:
    key = _key(request)
    if key not in CONSENT_EXEMPT and needs_consent(ctx.member):
        raise ConsentRequired()
    if settings.BETA_MODE and key not in BETA_EXEMPT_EXACT and not request.path_info.startswith(BETA_EXEMPT_PREFIXES):
        from apps.beta import services

        if not services.has_access(ctx.member, ctx.verified_email):
            raise BetaRequired()
