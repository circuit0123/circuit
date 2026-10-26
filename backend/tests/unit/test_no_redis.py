"""Production can run with no Redis at all (the beta): REDIS_URL empty means the app takes the same path as when Redis is down."""

import pytest
from django.test import Client

from core import cache, ratelimit
from core.errors import RateLimited
from tests.unit.test_startup_checks import PROD, make


@pytest.fixture
def no_redis(settings):
    settings.REDIS_URL = ""
    cache.set_cache(None)  # the next get_cache() builds from the empty setting
    yield cache.get_cache()
    cache.set_cache(None)


def test_production_starts_with_no_redis_url_and_a_url_must_still_be_tls():
    assert make(**{**PROD, "redis_url": ""}).redis_url == ""
    with pytest.raises(ValueError, match="rediss://"):
        make(**{**PROD, "redis_url": "redis://default:p@x.upstash.io:6379"})


def test_a_cache_without_redis_is_a_silent_miss(no_redis):
    assert not no_redis.configured
    assert no_redis.get_json("k") is None
    assert no_redis.set_json("k", {"a": 1}, essential=True) is False
    assert no_redis.incr_window("k", 60) is None and no_redis.ttl("k") is None
    assert no_redis.ping() is False
    no_redis.delete("k")
    no_redis.flush_prefix("k")


def test_rate_limits_still_stop_a_flood_by_counting_in_postgres(no_redis, db, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "settings_write": (2, 60)}
    ratelimit.check_rate("m1", "settings_write")
    ratelimit.check_rate("m1", "settings_write")
    with pytest.raises(RateLimited):
        ratelimit.check_rate("m1", "settings_write")


def test_no_per_request_warning_when_redis_is_not_configured(no_redis, db, settings, caplog, capsys):
    ratelimit.check_rate("m2", "settings_write")
    assert "rate_limit_postgres_fallback" not in capsys.readouterr().out + caplog.text


def test_ready_is_ok_and_says_redis_is_not_configured(no_redis, db):
    body = Client().get("/ready").json()
    assert body == {"status": "ok", "postgres": "ok", "redis": "not_configured"}


def test_deps_health_reports_not_configured_without_failing(no_redis, db):
    r = Client().get("/api/health/deps")
    assert r.status_code == 200 and r.json()["redis"] == "not_configured" and r.json()["status"] == "ok"


def test_the_one_startup_warning_is_logged(settings, capsys):
    from django.apps import apps

    settings.REDIS_URL = ""
    apps.get_app_config("core").ready()
    assert "redis_not_configured" in capsys.readouterr().out
