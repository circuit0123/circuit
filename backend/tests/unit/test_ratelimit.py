from datetime import timedelta

import pytest
import redis
from django.utils import timezone

from core import cache
from core.errors import RateLimited
from core.models import RateLimitHit
from core.ratelimit import check_rate

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def tight_limits(settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "report": (3, 60), "claim": (2, 60)}


def test_allows_up_to_limit_then_429():
    for _ in range(3):
        check_rate(1, "report")
    with pytest.raises(RateLimited) as e:
        check_rate(1, "report")
    assert e.value.status == 429 and e.value.details["retry_after"] <= 60


def test_limits_are_per_member_and_per_action():
    for _ in range(3):
        check_rate(1, "report")
    check_rate(2, "report")  # another member
    check_rate(1, "claim")  # another action


def test_unknown_action_is_a_bug_not_a_pass():
    with pytest.raises(KeyError):
        check_rate(1, "typo")


class DownRedis:
    def pipeline(self):
        raise redis.ConnectionError("down")

    def ttl(self, key):
        raise redis.ConnectionError("down")


def test_falls_back_to_postgres_when_redis_is_down(caplog):
    cache.set_cache(cache.Cache(DownRedis()))
    for _ in range(3):
        check_rate(1, "report")
    with pytest.raises(RateLimited):
        check_rate(1, "report")
    check_rate(2, "report")
    assert RateLimitHit.objects.filter(key="rl:report:1").count() == 3  # denied requests are not recorded


def test_postgres_fallback_ignores_old_hits_and_prunes():
    cache.set_cache(cache.Cache(DownRedis()))
    old = [RateLimitHit.objects.create(key="rl:report:1") for _ in range(5)]
    RateLimitHit.objects.filter(pk__in=[o.pk for o in old]).update(created_at=timezone.now() - timedelta(days=2))
    check_rate(1, "report")  # five hits from two days ago neither count nor survive
    assert RateLimitHit.objects.count() == 1
