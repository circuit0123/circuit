"""Feature flags: ship code dark, switch features on per audience (CLAUDE.md "Feature flags").

One check everywhere:
    flags.enabled("circuits", member)   # services
    @require_flag("circuits")           # on each Ninja operation of a flagged router
    flags.enabled("circuits")           # jobs (no member = the `everyone` audience only)

The default audience per flag comes from the FEATURES setting; a super admin overrides it in Django admin
(FeatureFlag rows). Overrides are cached in Redis for 60 s; if Redis is down we read Postgres.
This module must stay importable before Django is configured (circuit/config.py validates FEATURES),
so models and settings are imported inside functions.
"""

import functools

OFF, TESTERS, EVERYONE = "off", "testers", "everyone"
AUDIENCES = (OFF, TESTERS, EVERYONE)

# flag -> the flag it needs (it cannot be on while that one is off)
FLAGS: dict[str, str | None] = {
    "pulse": None,
    "daily_drop": None,
    "circuits": None,
    "investor_mode": None,
    "partner_mode": None,
    "promotions": "pulse",
    "payments": "promotions",
}

CACHE_KEY = "flags:v1"
CACHE_TTL = 60


def parse_features(text: str) -> dict[str, str]:
    """'pulse:everyone,circuits:testers' -> every flag with its audience (unlisted = off). Bad input raises."""
    result = dict.fromkeys(FLAGS, OFF)
    for part in (p.strip() for p in text.split(",")):
        if not part:
            continue
        name, _, audience = part.partition(":")
        if name not in FLAGS:
            raise ValueError(f"FEATURES: unknown flag '{name}' (known: {', '.join(FLAGS)})")
        if audience not in AUDIENCES:
            raise ValueError(f"FEATURES: audience for '{name}' must be one of {', '.join(AUDIENCES)}")
        result[name] = audience
    return result


def check_dependencies(audiences: dict[str, str]) -> None:
    """A flag that is on needs its dependency on too. Raises ValueError naming the pair."""
    for name, needs in FLAGS.items():
        if needs and audiences[name] != OFF and audiences[needs] == OFF:
            raise ValueError(f"Feature flag '{name}' is on but it needs '{needs}', which is off")


def defaults() -> dict[str, str]:
    from django.conf import settings

    return parse_features(settings.FEATURES)


def overrides() -> dict[str, str]:
    """Admin overrides: Redis copy first, Postgres when Redis has nothing or is down."""
    from core.cache import get_cache
    from core.models import FeatureFlag

    cache = get_cache()
    cached = cache.get_json(CACHE_KEY)
    if cached is not None:
        return cached
    rows = dict(FeatureFlag.objects.values_list("name", "audience"))
    cache.set_json(CACHE_KEY, rows, ttl=CACHE_TTL)
    return rows


def audiences() -> dict[str, str]:
    merged = defaults()
    merged.update({n: a for n, a in overrides().items() if n in FLAGS and a in AUDIENCES})
    return merged


def _allows(audience: str, member) -> bool:
    if audience == EVERYONE:
        return True
    return audience == TESTERS and member is not None and bool(getattr(member, "is_tester", False))


def enabled(name: str, member=None) -> bool:
    if name not in FLAGS:
        raise KeyError(f"unknown feature flag '{name}'")
    return _allows(audiences()[name], member)


def all_for(member=None) -> dict[str, bool]:
    current = audiences()
    return {name: _allows(current[name], member) for name in FLAGS}


def require_flag(name: str):
    """Decorator for a Ninja operation: 404 `feature_off` when the flag is off for the caller."""
    if name not in FLAGS:
        raise KeyError(f"unknown feature flag '{name}'")

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            from core.auth import current_member
            from core.errors import ApiError

            if not enabled(name, current_member(request)):
                raise ApiError(404, "feature_off", "This feature is not available")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def set_audience(name: str, audience: str, actor=None, note: str | None = None, via: str = "admin") -> None:
    """The one way to change a flag (admin and CLI). Validates, saves, audit-logs and clears the cache."""
    from apps.moderation.models import AuditLog
    from core.cache import get_cache
    from core.models import FeatureFlag

    if name not in FLAGS:
        raise ValueError(f"Unknown flag '{name}'")
    if audience not in AUDIENCES:
        raise ValueError(f"Audience must be one of {', '.join(AUDIENCES)}")
    before = audiences()
    check_dependencies({**before, name: audience})
    # Switching promotions/payments off while a paid campaign or an open order exists is refused once those
    # tables exist (Stage 4d/4e); there is nothing in flight to protect yet.
    row, _ = FeatureFlag.objects.get_or_create(name=name, defaults={"audience": audience})
    row.audience = audience
    if note is not None:
        row.note = note
    row.updated_by = actor
    row.save()
    AuditLog.objects.create(
        actor=actor,
        action="flag.set",
        target_type="core.featureflag",
        target_id=name,
        payload={"from": before[name], "to": audience, "via": via},
    )
    get_cache().delete(CACHE_KEY)
