"""Per-member rate limits (PRODUCTION.md §3). One helper, called by the endpoint before it does the work.

Limits live in settings.RATE_LIMITS as (max requests, window seconds). Redis counts them;
if Redis is down we count in Postgres instead (CLAUDE.md: Redis is disposable) and log a warning.
"""

import hashlib
import hmac
import ipaddress
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


def client_ip(request) -> str:
    """The caller's address. With TRUSTED_PROXY_HOPS = n we take the n-th entry from the right of X-Forwarded-For: the entries to
    its left were written by the caller and can be anything. With 0 (dev) only the socket address counts."""
    hops = settings.TRUSTED_PROXY_HOPS
    candidates = []
    if hops:
        parts = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(parts) >= hops:
            candidates.append(parts[-hops])
    candidates.append(request.META.get("REMOTE_ADDR", ""))
    for raw in candidates:
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            continue
    return "unknown"


def ip_key(request) -> str:
    """Bucket name for a caller's address. Hashed, so neither Redis nor the Postgres fallback stores a raw IP."""
    digest = hmac.new(settings.SECRET_KEY.encode(), b"rate-limit-ip-v1|" + client_ip(request).encode(), hashlib.sha256)
    return "ip-" + digest.hexdigest()[:20]


def check_rate(who: int | str, action: str) -> None:
    """Count this request and raise RateLimited (429) once the caller is over the limit for `action`.

    `who` is a member id, or `ip_key(request)` for endpoints with no signed-in member.
    """
    limit, window = settings.RATE_LIMITS[action]  # KeyError on a typo is a bug, not a user error
    key = f"rl:{action}:{who}"
    cache = get_cache()
    count = cache.incr_window(key, window)
    if count is None:
        log.warning("rate_limit_postgres_fallback", action=action)
        count = _count_in_postgres(key, window, limit)
    if count > limit:
        raise RateLimited(retry_after=cache.ttl(key) or window)
