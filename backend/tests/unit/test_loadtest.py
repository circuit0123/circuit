"""The load test's maths and its refusals. No network: httpx.MockTransport stands in for the server."""

import asyncio

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core import loadtest


def test_percentile():
    assert loadtest.percentile([], 95) == 0.0
    assert loadtest.percentile([10], 95) == 10
    values = list(range(1, 101))
    assert loadtest.percentile(values, 50) == 50
    assert loadtest.percentile(values, 95) == 95


def _stats(name, samples):
    st = loadtest.Stats()
    for ms, status in samples:
        st.add(ms, status)
    return {name: st}


def test_summary_pass_fail_and_targets():
    ok = loadtest.summarise(_stats("GET /api/jobs", [(100, 200)] * 20))[0]
    assert ok["pass"] and ok["target_ms"] == 800 and ok["error_pct"] == 0
    slow = loadtest.summarise(_stats("GET /api/jobs", [(900, 200)] * 20))[0]
    assert not slow["pass"]
    cached = loadtest.summarise(_stats("GET /api/matches", [(400, 200)] * 20))[0]
    assert cached["target_ms"] == 300 and not cached["pass"]


def test_errors_and_rate_limits_are_counted_apart():
    rows = loadtest.summarise(_stats("POST /x", [(10, 200)] * 8 + [(10, 429), (10, 500)]))
    row = rows[0]
    assert row["rate_limited"] == 1 and row["error_pct"] == 10.0 and not row["pass"]
    only_limited = loadtest.summarise(_stats("POST /x", [(10, 200)] * 9 + [(10, 429)]))[0]
    assert only_limited["pass"] and only_limited["rate_limited"] == 1


def _check(env_response):
    transport = httpx.MockTransport(env_response)

    async def go():
        async with httpx.AsyncClient(transport=transport) as client:
            return await loadtest.check_not_production(client, "http://api.test")

    return asyncio.run(go())


def test_refuses_production():
    assert "PRODUCTION" in _check(lambda r: httpx.Response(200, json={"env": "production"}))


def test_refuses_when_it_cannot_tell():
    assert "could not read" in _check(lambda r: httpx.Response(502, text="bad gateway"))

    def boom(request):
        raise httpx.ConnectError("down")

    assert "could not read" in _check(boom)


def test_allows_staging_and_dev():
    assert _check(lambda r: httpx.Response(200, json={"env": "staging"})) is None
    assert _check(lambda r: httpx.Response(200, json={"env": "dev"})) is None


def test_main_exits_2_for_production_and_sends_no_other_request(tmp_path, monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={"env": "production"})

    real = httpx.AsyncClient
    monkeypatch.setattr(loadtest.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    tokens = tmp_path / "t"
    tokens.write_text("abc\n")
    code = loadtest.main(["--url", "http://api.test", "--tokens", str(tokens), "--lat", "1", "--lng", "2"])
    assert code == 2 and seen == ["/api/config"]


@pytest.mark.django_db
def test_token_command_writes_tokens_for_seeded_members(tmp_path, settings):
    from apps.accounts.models import Member

    Member.objects.create(auth_user_id="00000000-0000-0000-0000-000000000001", role="student", display_name="A", city="X")
    settings.DEMO_AUTH, settings.ENV = True, "dev"
    out = tmp_path / "tokens"
    call_command("load_test_tokens", "--count", "5", "--out", str(out))
    assert len(out.read_text().split()) == 1


@pytest.mark.parametrize("env", ["staging", "production"])
def test_token_command_refuses_outside_dev_and_demo(tmp_path, settings, env):
    settings.DEMO_AUTH, settings.ENV = True, env
    with pytest.raises(CommandError):
        call_command("load_test_tokens", "--out", str(tmp_path / "t"))
