import fakeredis
import pytest
from django.core.management import CommandError, call_command
from pydantic import ValidationError

from apps.moderation.models import AuditLog
from circuit.config import Config
from core import cache, flags
from core.models import FeatureFlag
from tests.unit.test_config import BASE

pytestmark = pytest.mark.django_db
ALL = ",".join(f"{n}:everyone" for n in flags.FLAGS)


def make(**over):
    return Config(_env_file=None, **{**BASE, **over})


# -- FEATURES parsing and startup rules ------------------------------------------------------
def test_unlisted_flags_are_off():
    parsed = flags.parse_features("pulse:everyone,circuits:testers")
    assert parsed["pulse"] == "everyone" and parsed["circuits"] == "testers" and parsed["payments"] == "off"
    assert set(parsed) == set(flags.FLAGS)


@pytest.mark.parametrize("text", ["nonsense:everyone", "pulse:sometimes", "pulse"])
def test_bad_features_refuse_to_start(text):
    with pytest.raises(ValidationError, match="FEATURES"):
        make(features=text)


def test_a_flag_on_without_its_dependency_refuses_to_start():
    with pytest.raises(ValidationError, match="needs 'pulse'"):
        make(features="promotions:everyone")
    with pytest.raises(ValidationError, match="needs 'promotions'"):
        make(features="pulse:everyone,payments:testers")
    assert make(features="pulse:everyone,promotions:testers,payments:testers").features


def test_live_razorpay_key_is_refused_outside_production():
    with pytest.raises(ValidationError, match="live keys"):
        make(razorpay_key_id="rzp_live_abc")
    assert make(razorpay_key_id="rzp_test_abc").razorpay_key_id


def test_payments_in_production_needs_a_live_key():
    prod = dict(env="production", supabase_url="https://x.supabase.co", storage_provider="supabase")
    prod.update(supabase_service_role_key="k", allowed_hosts="api.example.com", cors_allowed_origins="https://app.example.com")
    with pytest.raises(ValidationError, match="live key"):
        make(**prod, features=ALL, razorpay_key_id="rzp_test_abc")
    assert make(**prod, features=ALL, razorpay_key_id="rzp_live_abc")
    assert make(**prod, features="pulse:everyone")  # payments off: no key needed


# -- audiences -------------------------------------------------------------------------------
def test_off_testers_everyone(settings, make_member):
    tester, other = make_member("student", is_tester=True), make_member("student")
    settings.FEATURES = "pulse:off,daily_drop:testers,circuits:everyone"
    assert not flags.enabled("pulse", tester) and not flags.enabled("pulse")
    assert flags.enabled("daily_drop", tester) and not flags.enabled("daily_drop", other) and not flags.enabled("daily_drop")
    assert flags.enabled("circuits", other) and flags.enabled("circuits")


def test_an_override_beats_the_default_and_clears_the_cache(settings, make_member):
    settings.FEATURES = "circuits:everyone"
    m = make_member("student")
    assert flags.enabled("circuits", m)
    flags.set_audience("circuits", "off")
    assert not flags.enabled("circuits", m)  # no waiting for the 60 s cache
    flags.set_audience("circuits", "testers")
    assert not flags.enabled("circuits", m) and flags.enabled("circuits", make_member("student", is_tester=True))


def test_redis_down_reads_postgres(settings, monkeypatch):
    settings.FEATURES = ALL
    FeatureFlag.objects.create(name="pulse", audience="off")

    class Down(fakeredis.FakeRedis):
        def get(self, *a, **k):
            raise cache.redis.ConnectionError("down")

        def set(self, *a, **k):
            raise cache.redis.ConnectionError("down")

    cache.set_cache(cache.Cache(Down()))
    assert flags.enabled("pulse") is False and flags.enabled("circuits") is True


def test_set_audience_writes_the_audit_log():
    flags.set_audience("circuits", "testers", via="cli")
    log = AuditLog.objects.get(action="flag.set")
    assert log.target_id == "circuits" and log.payload["to"] == "testers" and log.payload["via"] == "cli"


def test_set_audience_refuses_a_change_that_breaks_a_dependency(settings):
    settings.FEATURES = ALL
    with pytest.raises(ValueError, match="needs 'pulse'"):
        flags.set_audience("pulse", "off")
    with pytest.raises(ValueError, match="Unknown"):
        flags.set_audience("nope", "off")
    with pytest.raises(ValueError, match="Audience"):
        flags.set_audience("pulse", "some")
    assert not FeatureFlag.objects.exists()


# -- manage.py flags -------------------------------------------------------------------------
def test_flags_command_lists_and_sets(settings, capsys):
    settings.FEATURES = ALL
    call_command("flags")
    out = capsys.readouterr().out
    assert "circuits" in out and "everyone" in out and "(needs pulse)" in out
    call_command("flags", "set", "circuits", "testers")
    call_command("flags")
    assert "testers" in capsys.readouterr().out
    with pytest.raises(CommandError):
        call_command("flags", "set", "circuits", "bogus")
    with pytest.raises(CommandError):
        call_command("flags", "set", "circuits")
