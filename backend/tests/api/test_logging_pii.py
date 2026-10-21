import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

SECRETS = ["leak.me@example.org", "Priya Secret Name", "A secret bio sentence"]


def test_no_pii_or_tokens_in_logs(make_member, make_org, token_for, capfd):
    org = make_org(code="ZZZZZZZZZZ")
    m = make_member("student", org=org, display_name="Priya Secret Name", bio="A secret bio sentence")
    token = token_for(m, email="leak.me@example.org", user_metadata={"full_name": "Priya Secret Name"})
    c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")
    c.get("/api/me")
    c.get("/api/organisations/mine")
    c.post("/api/organisations/join", {"code": "leak.me@example.org"}, content_type="application/json")  # 409, body has an email
    c.get("/api/organisations/mine/members?limit=oops")  # validation error path
    Client(HTTP_AUTHORIZATION="Bearer " + token[:-3] + "abc").get("/api/me")  # bad signature path
    out = capfd.readouterr().out
    assert out, "expected log output"
    for secret in [*SECRETS, token, token.split(".")[1], "ZZZZZZZZZZ"]:
        assert secret not in out, f"{secret!r} leaked into logs"
    lines = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    assert sum(1 for x in lines if x["event"] == "request") == 5  # one line per request


def test_rate_limit_and_jwks_warnings_have_no_pii(make_member, signing_key, supabase, capfd):
    from tests.conftest import make_token

    supabase["down"] = True
    m = make_member(display_name="Priya Secret Name")
    Client(HTTP_AUTHORIZATION=f"Bearer {make_token(m.auth_user_id, signing_key, email='leak.me@example.org')}").get("/api/me")
    out = capfd.readouterr().out
    assert "jwks_fetch_failed" in out and "leak.me@example.org" not in out and "Priya" not in out
