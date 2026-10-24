from django.conf import settings
from ninja import Router, Schema

from core import flags

router = Router()


class ConfigOut(Schema):
    env: str
    beta_mode: bool
    beta_access: bool
    features: dict[str, bool]


def _optional_context(request):
    """The signed-in caller, or None. A missing or bad token is just an anonymous visitor, never a 401."""
    from core.auth import SupabaseAuth
    from core.errors import ApiError

    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return SupabaseAuth().identify(request, token)  # no beta gate: this is how the app learns it is gated
    except ApiError:  # a suspended member sees the public config
        return None


@router.get(
    "",
    response=ConfigOut,
    auth=None,
    summary="App config",
    description="Public. Environment, whether the invite-only beta is on, whether the caller may get past the beta gate "
    "(`beta_access`; false for anonymous visitors while the beta is on) and which features are on for the caller "
    "(anonymous visitors get the `everyone` audience). The app hides screens for features that are off.",
)
def get_config(request):
    from apps.beta import gate

    ctx = _optional_context(request)
    member = ctx.member if ctx else None
    return {
        "env": settings.ENV,
        "beta_mode": settings.BETA_MODE,
        "beta_access": gate.passes(ctx) if ctx else not settings.BETA_MODE,
        "features": flags.all_for(member),
    }
