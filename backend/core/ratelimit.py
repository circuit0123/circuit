"""Per-member rate limits (PRODUCTION.md §3). One helper, called by the endpoint before it does the work.

Limits live in settings.RATE_LIMITS as (max requests, window seconds). Redis counts them;
if Redis is down we count in Postgres instead (CLAUDE.md: Redis is disposable) and log a warning.
"""

from datetime import timedelta

import structlog
from django.conf import settings
from django.utils import timezone

from core.cache import get_cache
from core.errors import RateLimited

log = structlog.get_logger("ratelimit")
PRUNE_AFTER = timedelta(days=1)  # longer than every window in settings


def _count_in_postgres(key: str, window: int, limit: int) -> int:
    """Hits in the window including this one. Requests over the limit are NOT recorded, so a flood cannot grow the table."""
    from core.models import RateLimitHit

    now = timezone.now()
    RateLimitHit.objects.filter(key=key, created_at__lt=now - PRUNE_AFTER).delete()
    recent = RateLimitHit.objects.filter(key=key, created_at__gte=now - timedelta(seconds=window)).count()
    if recent < limit:
        RateLimitHit.objects.create(key=key)
    return recent + 1


def check_rate(member_id: int, action: str) -> None:
    """Count this request and raise RateLimited (429) once the member is over the limit for `action`."""
    limit, window = settings.RATE_LIMITS[action]  # KeyError on a typo is a bug, not a user error
    key = f"rl:{action}:{member_id}"
    cache = get_cache()
    count = cache.incr_window(key, window)
    if count is None:
        log.warning("rate_limit_postgres_fallback", action=action)
        count = _count_in_postgres(key, window, limit)
    if count > limit:
        raise RateLimited(retry_after=cache.ttl(key) or window)
