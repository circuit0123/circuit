"""LLM_PROVIDER=none (no language model: manual pickers) and LLM_DAILY_CALL_LIMIT (a spending cap that falls back to the same pickers)."""

import json
from datetime import timedelta

import pytest
from pydantic import BaseModel, ValidationError

from core import llm, usage
from core.models import UsageCounter
from tests.unit.test_config import DEPLOYED, make

pytestmark = pytest.mark.django_db
BIO = {"bio": "I build a farm-tech marketplace and need help with fundraising and a technical co-founder."}


class Out(BaseModel):
    slugs: list[str]


# -- LLM_PROVIDER=none ---------------------------------------------------------------------------
def test_none_returns_nothing_without_calling_any_provider(settings, fake_llm):
    settings.LLM_PROVIDER = "none"
    fake_llm.response = json.dumps({"slugs": ["seo"]})
    assert llm.extract_json("s", "u", Out) is None
    assert fake_llm.calls == 0


def test_none_needs_no_database_and_no_key(settings, django_assert_num_queries):
    settings.LLM_PROVIDER = "none"
    settings.LLM_DAILY_CALL_LIMIT = 5
    llm.set_llm(None)
    with django_assert_num_queries(0):
        assert llm.extract_json("s", "u", Out) is None


def test_the_none_provider_exists_and_refuses_to_be_called(settings):
    settings.LLM_PROVIDER = "none"
    llm.set_llm(None)
    provider = llm.get_llm()
    assert isinstance(provider, llm.NoLLM)
    with pytest.raises(RuntimeError, match="LLM_PROVIDER=none"):
        provider.complete("s", "u")


def test_onboarding_with_none_uses_the_manual_pickers(settings, lists, make_member, client_for, fake_llm):
    settings.LLM_PROVIDER = "none"
    r = client_for(make_member()).post("/api/onboarding/extract", json.dumps(BIO))
    assert r.status_code == 200
    assert r.json() == {"source": "manual", "suggestions": {"needs": [], "offers": [], "skills": [], "traits": []}}
    assert fake_llm.calls == 0


@pytest.mark.parametrize("env", ["staging", "production"])
def test_none_is_allowed_when_deployed_without_any_api_key(env):
    config = make(**{**DEPLOYED, "env": env, "llm_provider": "none", "groq_api_key": ""})
    assert config.llm_provider == "none"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_other_providers_still_need_their_key_when_deployed(env):
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        make(**{**DEPLOYED, "env": env, "llm_provider": "groq", "groq_api_key": ""})


# -- the daily cap -------------------------------------------------------------------------------
def test_calls_below_the_cap_go_through_and_are_counted(settings, fake_llm):
    settings.LLM_DAILY_CALL_LIMIT = 3
    fake_llm.response = json.dumps({"slugs": ["seo"]})
    for _ in range(3):
        assert llm.extract_json("s", "u", Out) == Out(slugs=["seo"])
    assert usage.count("llm_calls") == 3 and fake_llm.calls == 3


def test_past_the_cap_it_falls_back_without_calling_the_provider(settings, fake_llm, capfd):
    settings.LLM_DAILY_CALL_LIMIT = 2
    fake_llm.response = json.dumps({"slugs": ["seo"]})
    results = [llm.extract_json("s", "u", Out) for _ in range(4)]
    assert results[:2] == [Out(slugs=["seo"])] * 2 and results[2:] == [None, None]
    assert fake_llm.calls == 2  # the provider (and the bill) saw only the first two
    assert "llm.cap_reached" in capfd.readouterr().out


def test_the_cap_resets_the_next_day(settings, fake_llm):
    settings.LLM_DAILY_CALL_LIMIT = 1
    fake_llm.response = json.dumps({"slugs": ["seo"]})
    yesterday = usage.today() - timedelta(days=1)
    usage.bump("llm_calls", 50, day=yesterday)
    assert llm.extract_json("s", "u", Out) == Out(slugs=["seo"])
    assert llm.extract_json("s", "u", Out) is None


def test_zero_means_no_cap_and_touches_no_counter(settings, fake_llm):
    settings.LLM_DAILY_CALL_LIMIT = 0
    fake_llm.response = json.dumps({"slugs": ["seo"]})
    for _ in range(5):
        assert llm.extract_json("s", "u", Out) is not None
    assert UsageCounter.objects.count() == 0


def test_retries_after_a_failure_each_count_as_a_call(settings, fake_llm, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    settings.LLM_DAILY_CALL_LIMIT = 100
    fake_llm.error = TimeoutError("slow")
    assert llm.extract_json("s", "u", Out) is None
    assert usage.count("llm_calls") == llm.MAX_ATTEMPTS


def test_a_broken_counter_never_blocks_onboarding(settings, fake_llm, monkeypatch):
    settings.LLM_DAILY_CALL_LIMIT = 1
    fake_llm.response = json.dumps({"slugs": ["seo"]})

    def broken(*a, **k):
        raise RuntimeError("database down")

    monkeypatch.setattr(usage, "bump", broken)
    assert llm.extract_json("s", "u", Out) == Out(slugs=["seo"])


def test_onboarding_over_the_cap_uses_the_manual_pickers(settings, lists, make_member, client_for, fake_llm):
    settings.LLM_DAILY_CALL_LIMIT = 1
    usage.bump("llm_calls", 1)
    fake_llm.response = json.dumps({"needs": ["fundraising"]})
    r = client_for(make_member()).post("/api/onboarding/extract", json.dumps(BIO))
    assert r.status_code == 200 and r.json()["source"] == "manual" and fake_llm.calls == 0


# -- the counter itself --------------------------------------------------------------------------
def test_bump_is_one_row_per_name_and_day():
    assert [usage.bump("x"), usage.bump("x"), usage.bump("x", 5), usage.bump("y")] == [1, 2, 7, 1]
    assert UsageCounter.objects.count() == 2
    assert usage.total("x", days=30) == 7
    usage.bump("x", 3, day=usage.today() - timedelta(days=40))
    assert usage.total("x", days=30) == 7 and usage.total("x", days=90) == 10


def test_the_daily_limit_comes_from_the_environment():
    assert make(llm_daily_call_limit=500).llm_daily_call_limit == 500
    with pytest.raises(ValidationError):
        make(llm_daily_call_limit=-1)
