"""Redis lean mode (REDIS_LEAN): fewer copies in Redis so Upstash's free 500,000 commands a month last. Redis only ever holds copies
of what Postgres knows, so the app behaves the same, just reads Postgres more."""

import fakeredis
import pytest

from core import flags
from core.cache import Cache

pytestmark = pytest.mark.django_db


class Spy:
    """Counts the Redis commands a Cache sends."""

    def __init__(self):
        self.inner = fakeredis.FakeRedis()
        self.commands = []

    def __getattr__(self, name):
        target = getattr(self.inner, name)
        if not callable(target):
            return target

        def call(*a, **k):
            self.commands.append(name)
            return target(*a, **k)

        return call


@pytest.fixture
def spy():
    return Spy()


@pytest.fixture
def lean(settings):
    settings.REDIS_LEAN = True
    settings.REDIS_LEAN_MAX_TTL = 600


def test_normal_mode_caches_everything_for_its_full_ttl(spy, settings):
    settings.REDIS_LEAN = False
    cache = Cache(spy)
    assert cache.set_json("k", {"a": 1}, ttl=21600)
    assert cache.get_json("k") == {"a": 1}
    assert 21000 < spy.inner.ttl("k") <= 21600


def test_lean_mode_skips_non_essential_caching_without_sending_a_command(spy, lean):
    cache = Cache(spy)
    assert cache.set_json("matches:1", [1, 2, 3], ttl=21600) is False
    assert cache.get_json("matches:1") is None
    assert spy.commands == [] and spy.inner.keys() == []


def test_lean_mode_still_reads_nothing_that_was_stored_earlier_by_a_full_mode_instance(spy, lean, settings):
    settings.REDIS_LEAN = False
    Cache(spy).set_json("matches:1", [1], ttl=100)
    settings.REDIS_LEAN = True
    spy.commands.clear()
    assert Cache(spy).get_json("matches:1") is None and spy.commands == []  # the caller recomputes from Postgres


def test_essential_entries_are_kept_but_for_ten_minutes_at_most(spy, lean):
    cache = Cache(spy)
    assert cache.set_json("flags", {"x": 1}, ttl=21600, essential=True)
    assert cache.get_json("flags", essential=True) == {"x": 1}
    assert 0 < spy.inner.ttl("flags") <= 600


def test_a_short_essential_ttl_is_left_alone(spy, lean):
    Cache(spy).set_json("flags", 1, ttl=60, essential=True)
    assert 0 < spy.inner.ttl("flags") <= 60


def test_counters_are_behaviour_not_copies_and_always_run(spy, lean):
    cache = Cache(spy)
    assert [cache.incr_window("rl:1", 60), cache.incr_window("rl:1", 60)] == [1, 2]


def test_feature_flags_keep_working_and_stay_cached_in_lean_mode(lean, settings, spy):
    from core.cache import set_cache

    set_cache(Cache(spy))
    settings.FEATURES = "pulse:everyone"
    assert flags.enabled("pulse")
    assert flags.enabled("pulse")
    assert spy.inner.ttl(flags.CACHE_KEY) is not None and 0 < spy.inner.ttl(flags.CACHE_KEY) <= 600


def test_match_lists_come_from_postgres_in_lean_mode(lean, make_member, spy):
    from apps.matching import services
    from core.cache import set_cache

    set_cache(Cache(spy))
    me = make_member("student")
    assert services.matches_for(me) is not None
    assert services.cache_key(me.pk).encode() not in spy.inner.keys() and spy.inner.keys() == []


def test_the_deploy_files_turn_lean_mode_on_for_every_cloud_environment():
    import tomllib
    from pathlib import Path

    shared = tomllib.loads((Path(__file__).resolve().parents[3] / "deploy/gcp/app.toml").read_text())
    assert shared["env"]["REDIS_LEAN"] == "true" and shared["env"]["MEDIA_WEBP_QUALITY"] == "75"
