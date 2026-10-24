from django.conf import settings
from ninja import Router, Schema

from core import flags

router = Router()


class ConfigOut(Schema):
    env: str
    beta_mode: bool
    features: dict[str, bool]


def _optional_member(request):
    """The signed-in member, or None. A missing or bad token is just an anonymous visitor, never a 401."""
    from core.auth import SupabaseAuth
    from core.errors import ApiError

    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        ctx = SupabaseAuth().authenticate(request, token)
    except ApiError:  # a suspended member sees the public config
        return None
    return ctx.member if ctx else None


@router.get(
    "",
    response=ConfigOut,
    auth=None,
    summary="App config",
    description="Public. Environment, whether the invite-only beta is on, and which features are on for the caller "
    "(anonymous visitors get the `everyone` audience). The app hides screens for features that are off.",
)
def get_config(request):
    member = _optional_member(request)
    return {"env": settings.ENV, "beta_mode": settings.BETA_MODE, "features": flags.all_for(member)}
