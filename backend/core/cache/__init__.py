"""Cache + counters behind one interface. Redis is disposable.

Every method swallows Redis errors, logs a warning and behaves like a cache miss,
so callers fall back to Postgres (the source of truth).

LEAN MODE (REDIS_LEAN=true, for Upstash's free plan: 500,000 commands a month). Redis only ever holds copies of what Postgres
knows, so lean mode simply keeps fewer copies:
  - `get_json` / `set_json` do nothing (no Redis command at all) unless the caller says `essential=True`;
  - an essential entry lives at most REDIS_LEAN_MAX_TTL seconds (default 600), so Redis never holds much;
  - counters (`incr_window`: rate limits, the once-a-day view count) always run: they are behaviour, not a copy.
Essential = read on every request and expensive to rebuild (the feature-flag overrides). Everything else (match lists, partner
dashboards, signed image links) is rebuilt from Postgres or storage when it is not cached.
"""

import json
from typing import Any

import redis
import structlog
from django.conf import settings

log = structlog.get_logger("cache")


class Cache:
    def __init__(self, client):
        self.client = client

    def _safe(self, op: str, fn, default=None):
        try:
            return fn()
        except redis.RedisError as exc:
            log.warning("redis_unavailable", op=op, error=type(exc).__name__)
            return default

    def ping(self) -> bool:
        return bool(self._safe("ping", self.client.ping, False))

    @staticmethod
    def lean() -> bool:
        return bool(getattr(settings, "REDIS_LEAN", False))

    def get_json(self, key: str, *, essential: bool = False) -> Any | None:
        if self.lean() and not essential:
            return None  # lean mode: a miss without asking Redis
        raw = self._safe("get", lambda: self.client.get(key))
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any, ttl: int = 3600, *, essential: bool = False) -> bool:
        if self.lean():
            if not essential:
                return False  # lean mode: keep no copy
            ttl = min(ttl, settings.REDIS_LEAN_MAX_TTL)
        return bool(self._safe("set", lambda: self.client.set(key, json.dumps(value), ex=ttl), False))

    def delete(self, key: str) -> None:
        self._safe("delete", lambda: self.client.delete(key))

    def incr_window(self, key: str, window_seconds: int) -> int | None:
        """Fixed-window counter. Returns the new count, or None if Redis is down."""

        def run() -> int:
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            return int(pipe.execute()[0])

        return self._safe("incr", run)

    def ttl(self, key: str) -> int | None:
        """Seconds until `key` expires, or None if unknown (missing key or Redis down)."""
        seconds = self._safe("ttl", lambda: self.client.ttl(key))
        return seconds if isinstance(seconds, int) and seconds > 0 else None

    def flush_prefix(self, prefix: str) -> None:
        def run():
            for k in self.client.scan_iter(f"{prefix}*"):
                self.client.delete(k)

        self._safe("flush", run)


_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1, socket_connect_timeout=1))
    return _cache


def set_cache(cache: Cache | None) -> None:
    """Tests inject a fakeredis-backed Cache here."""
    global _cache
    _cache = cache
