"""The beta gate (F18). Called from one place: SupabaseAuth.authenticate, when BETA_MODE is on.

Public endpoints (/api/health*, /api/config, /api/waitlist, /api/demo/*) are `auth=None`, so they never reach the gate.
Of the protected ones, only these stay open to a signed-in member without access, because the app needs them to show
"Got an invite code?" and let the person in: who am I, redeem a code, and the onboarding helpers.
"""

from django.conf import settings
from django.http import HttpRequest

from apps.beta import services
from core.errors import BetaRequired

EXEMPT_PREFIXES = ("/api/onboarding/",)
EXEMPT_EXACT = {("GET", "/api/me"), ("POST", "/api/beta/redeem")}


def is_exempt(request: HttpRequest) -> bool:
    path = request.path_info
    return (request.method, path) in EXEMPT_EXACT or path.startswith(EXEMPT_PREFIXES)


def passes(ctx) -> bool:
    """True if this caller is let in right now (always true while BETA_MODE is off). May grant access from the allowlist."""
    return not settings.BETA_MODE or services.has_access(ctx.member, ctx.verified_email)


def enforce(request: HttpRequest, ctx) -> None:
    if not is_exempt(request) and not services.has_access(ctx.member, ctx.verified_email):
        raise BetaRequired()
