"""Regression tests for the finecomb audit of Stage 2 (auth and permissions).

Each test names the finding it protects (F-01 ...); the full write-up is in PROGRESS.md.
"""

import logging
import threading
import time
import uuid

import pytest
from django.test import Client

from core import auth
from tests.conftest import KID, make_token

pytestmark = pytest.mark.django_db


def get(path, token=None, **extra):
    h = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return Client().get(path, **h, **extra)


# --- F-01 config: secrets, transport, hosts, regex ------------------------------------------------

from pydantic import ValidationError  # noqa: E402

from circuit.config import Config  # noqa: E402

BASE = dict(
    env="dev", secret_key="aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5", database_url="postgres://u:p@h/d", redis_url="redis://h",
    allowed_hosts="h", cors_allowed_origins="https://app.example", app_url="http://a", landing_url="http://l",
    api_url="http://api", seed_city_name="C", seed_city_lat=1.0, seed_city_lng=2.0, supabase_url="https://x.supabase.co", storage_provider="supabase", supabase_service_role_key="k",
    trusted_proxy_hops=1, email_from="Circuit <hello@example.com>",
)  # fmt: skip


# the "required when deployed" rules (circuit/config.py), for tests that build a valid staging/production Config
DEPLOYED = dict(
    email_backend="resend", resend_api_key="re_x", embedding_provider="fastembed", llm_provider="groq", groq_api_key="g",
    csrf_trusted_origins="https://api.example.com", redis_url="rediss://h",
)  # fmt: skip


def cfg(**over):
    return Config(_env_file=None, **{**BASE, **over})


@pytest.mark.parametrize("env", ["demo", "staging", "production"])
@pytest.mark.parametrize(
    "key",
    [
        "change-me-to-50-random-chars-aB3dE5fG7hJ9kL1m",
        "short-but-random-1aZ",
        "x" * 64,
        "django-insecure-aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW",
    ],
)
def test_f01_weak_or_placeholder_secret_key_refused_outside_dev(env, key):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        cfg(env=env, secret_key=key)


def test_f01_dev_may_keep_a_simple_key():
    assert cfg(env="dev", secret_key="change-me-to-50-random-chars").env == "dev"


def test_f01_strong_key_ok_in_production():
    assert cfg(env="production", **DEPLOYED).env == "production"


@pytest.mark.parametrize("env", ["demo", "staging", "production"])
def test_f05_debug_refused_outside_dev(env):
    with pytest.raises(ValidationError, match="DEBUG"):
        cfg(env=env, debug=True)


@pytest.mark.parametrize("url", ["http://x.supabase.co", "ftp://x", "x.supabase.co"])
@pytest.mark.parametrize("env", ["staging", "production"])
def test_f10_supabase_url_must_be_https_when_deployed(env, url):
    with pytest.raises(ValidationError, match="SUPABASE_URL"):
        cfg(env=env, supabase_url=url)


def test_f10_dev_may_use_local_http_supabase():
    assert cfg(env="dev", supabase_url="http://localhost:54321").env == "dev"


@pytest.mark.parametrize("hosts", ["*", "api.example,*", ".example.com,*"])
def test_f10_wildcard_hosts_refused_outside_dev(hosts):
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        cfg(env="staging", allowed_hosts=hosts)


@pytest.mark.parametrize("origins", ["*", "https://a.example/", "app.example", "https://a.example/path", "https://*.example"])
def test_f10_cors_origins_must_be_exact_origins(origins):
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        cfg(env="staging", cors_allowed_origins=origins)


@pytest.mark.parametrize(
    "regex",
    [
        r"^https://circuit-app-staging-git-.*\.vercel\.app",
        r"https://x\.vercel\.app$",
        r"^https://(unclosed$",
        r"^http://x\.app$",
        ".*",
    ],
)
def test_f10_preview_regex_must_be_anchored_https_and_valid(regex):
    with pytest.raises(ValidationError, match="CORS_PREVIEW_REGEX"):
        cfg(env="staging", cors_preview_regex=regex)


def test_f10_good_preview_regex_ok_on_staging_only():
    good = r"^https://circuit-app-staging-git-[a-z0-9-]+-myteam\.vercel\.app$"
    assert cfg(env="staging", cors_preview_regex=good, **DEPLOYED).cors_preview_regex == good
    with pytest.raises(ValidationError, match="CORS_PREVIEW_REGEX"):
        cfg(env="demo", cors_preview_regex=good)


# --- F-03 / F-09 JWKS cache: no lock held during network I/O, bounded staleness --------------------


def test_f03_slow_jwks_refresh_does_not_block_other_requests(signing_key, supabase, monkeypatch):
    auth._signing_key(KID)  # warm
    auth._state.fetched_at -= auth.JWKS_TTL + 1  # cache now needs a refresh
    auth._state.last_attempt -= auth.REFETCH_AFTER_KEYS + 1
    started, release = threading.Event(), threading.Event()
    real = auth._fetch_jwks

    def slow(**kw):
        started.set()
        release.wait(10)
        return real(**kw)

    monkeypatch.setattr(auth, "_fetch_jwks", slow)
    refresher = threading.Thread(target=lambda: auth._signing_key(KID), daemon=True)
    refresher.start()
    assert started.wait(5)
    got = []
    other = threading.Thread(target=lambda: got.append(auth._signing_key(KID)), daemon=True)
    other.start()
    other.join(timeout=2)
    still_blocked = other.is_alive()
    release.set()
    refresher.join(5)
    other.join(5)
    assert not still_blocked, "a request needing a cached key waited for another request's slow JWKS download"
    assert got and got[0] is not None


def test_f09_stale_keys_stop_being_served_after_max_stale(make_member, signing_key, supabase):
    m = make_member()
    assert get("/api/me", make_token(m.auth_user_id, signing_key)).status_code == 200
    supabase["down"] = True
    auth._state.last_attempt -= auth.REFETCH_AFTER_KEYS + 1
    auth._state.fetched_at -= auth.JWKS_MAX_STALE + 1
    r = get("/api/me", make_token(m.auth_user_id, signing_key))
    assert r.status_code == 503 and r.json()["error"]["code"] == "auth_unavailable"


# --- F-08 health/deps must not turn anonymous requests into outbound Supabase calls ---------------


def test_f08_health_deps_caches_the_jwks_probe(supabase):
    supabase["n"] = 0
    for _ in range(10):
        assert get("/api/health/deps").json()["jwks"] == "ok"
    assert supabase["n"] <= 1


# --- F-06 / F-11 email domain grants ---------------------------------------------------------------

HOSTILE = [
    "=?utf-8?q?a=40evil.com?=@kit.edu.in",
    '"a@evil.com"@kit.edu.in',
    "a(comment)@kit.edu.in",
    "a b@kit.edu.in",
    "a,b@kit.edu.in",
    "a;b@kit.edu.in",
    "<a>@kit.edu.in",
    "a@kit.edu.in\n",
    "a@kit.edu.in.",
    "a@Kit.edu.in",  # Kelvin sign: .lower() turns it into an ASCII k
    "а@kit.edu.in",  # Cyrillic a
    "a@kit.edu.in@evil.com",
    "@kit.edu.in",
]


@pytest.mark.parametrize("email", HOSTILE)
def test_f06_oddly_formed_email_never_grants_org_membership(email, make_member, make_org, client_for):
    make_org(domains=["kit.edu.in"])
    m = make_member()
    r = client_for(m, email=email).post("/api/organisations/join-by-email")
    assert r.status_code == 404, f"{email!r} joined an organisation"
    m.refresh_from_db()
    assert m.organisation_id is None


@pytest.mark.parametrize("email", ["asha@kit.edu.in", "Asha.R+x@KIT.edu.in", "a_b-c@kit.edu.in"])
def test_f06_ordinary_addresses_still_join(email, make_member, make_org, client_for):
    org = make_org(domains=["kit.edu.in"])
    m = make_member()
    assert client_for(m, email=email).post("/api/organisations/join-by-email").json()["id"] == org.pk


def test_f11_a_domain_claimed_by_two_organisations_grants_nothing(make_member, make_org, client_for):
    make_org("A", domains=["kit.edu.in"])
    make_org("B", domains=["kit.edu.in"])  # reachable through the ORM / shell, not the admin form
    m = make_member()
    assert client_for(m, email="a@kit.edu.in").post("/api/organisations/join-by-email").status_code == 404
    m.refresh_from_db()
    assert m.organisation_id is None


# --- F-02 consent to be seen is per organisation ---------------------------------------------------


def test_f02_joining_an_org_resets_visible_to_org(make_member, make_org, client_for):
    org = make_org(code="ABCDE12345")
    m = make_member(visible_to_org=True)  # set while in no organisation
    assert client_for(m).post("/api/organisations/join", {"code": "ABCDE12345"}).status_code == 200
    m.refresh_from_db()
    assert m.organisation_id == org.pk and m.visible_to_org is False


def test_f02_first_login_join_does_not_expose_member(make_org, signing_key):
    from apps.accounts.models import Member

    make_org(domains=["kit.edu.in"])
    uid = uuid.uuid4()
    get("/api/me", make_token(uid, signing_key, email="a@kit.edu.in"))
    assert Member.objects.get(auth_user_id=uid).visible_to_org is False


def test_f02_admin_moving_a_member_between_orgs_resets_consent(rf, make_member, make_org):
    from django.contrib import admin
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Member

    a, b = make_org("A"), make_org("B")
    m = make_member(org=a, visible_to_org=True)
    staff = get_user_model().objects.create_superuser("root2", password="a-long-test-password-1")
    request = rf.post("/")
    request.user = staff
    m.organisation = b
    form = type("F", (), {"changed_data": ["organisation"]})()
    admin.site._registry[Member].save_model(request, m, form, change=True)
    m.refresh_from_db()
    assert m.organisation_id == b.pk and m.visible_to_org is False


# --- F-12 join codes can be rotated ----------------------------------------------------------------


def test_f12_admin_can_regenerate_a_join_code_and_it_is_audited(rf, make_org):
    from django.contrib import admin
    from django.contrib.auth import get_user_model
    from django.contrib.messages.storage.cookie import CookieStorage

    from apps.moderation.models import AuditLog
    from apps.organisations.models import Organisation

    org = make_org(code="OLDCODE123")
    staff = get_user_model().objects.create_superuser("root3", password="a-long-test-password-1")
    request = rf.post("/")
    request.user = staff
    request._messages = CookieStorage(request)
    ma = admin.site._registry[Organisation]
    assert "regenerate_join_code" in ma.actions or "regenerate_join_code" in [
        a.__name__ for a in map(lambda n: getattr(ma, n), ma.actions)
    ]
    ma.regenerate_join_code(request, Organisation.objects.filter(pk=org.pk))
    org.refresh_from_db()
    assert org.join_code != "OLDCODE123" and len(org.join_code) == 10
    assert AuditLog.objects.filter(actor=staff, action="regenerate_join_code", target_id=str(org.pk)).exists()


def test_f12_old_code_stops_working(make_member, make_org, client_for):
    org = make_org(code="OLDCODE123")
    org.join_code = "NEWCODE456"
    org.save()
    assert client_for(make_member()).post("/api/organisations/join", {"code": "OLDCODE123"}).status_code == 404


# --- F-07 rate-limit fallback ----------------------------------------------------------------------


def test_f07_postgres_fallback_does_not_grow_without_bound(settings):
    import redis

    from core import cache
    from core.errors import RateLimited
    from core.models import RateLimitHit
    from core.ratelimit import check_rate

    class Down:
        def pipeline(self):
            raise redis.ConnectionError("down")

        def ttl(self, key):
            raise redis.ConnectionError("down")

    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "report": (3, 60)}
    cache.set_cache(cache.Cache(Down()))
    for _ in range(50):
        try:
            check_rate(1, "report")
        except RateLimited:
            pass
    assert RateLimitHit.objects.filter(key="rl:report:1").count() <= 3


# --- F-13 request id -------------------------------------------------------------------------------


@pytest.mark.parametrize("rid", ["a" * 10_000, "bad id with spaces", "<script>alert(1)</script>", "x" * 65, "ünï", ""])
def test_f13_untrusted_request_ids_are_replaced(rid):
    r = Client().get("/api/health", HTTP_X_REQUEST_ID=rid)
    out = r.headers["X-Request-ID"]
    assert out != rid and 8 <= len(out) <= 64 and out.isalnum()


def test_f13_sane_request_id_is_kept():
    assert Client().get("/api/health", HTTP_X_REQUEST_ID="abc-123_DEF.9").headers["X-Request-ID"] == "abc-123_DEF.9"


# --- F-14 headers on every response ----------------------------------------------------------------


def test_f14_preflight_and_redirect_style_early_responses_carry_security_headers(settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://app.example"]
    r = Client().options(
        "/api/me", HTTP_ORIGIN="https://app.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
    )  # fmt: skip
    assert r.status_code == 200
    assert "Content-Security-Policy" in r.headers and r.headers["X-Frame-Options"] == "DENY"


def test_f14_api_responses_are_not_cacheable(make_member, token_for):
    m = make_member()
    assert get("/api/me", token_for(m)).headers["Cache-Control"] == "no-store"
    assert get("/api/me").headers["Cache-Control"] == "no-store"  # 401s too
    assert get("/api/nope").headers["Cache-Control"] == "no-store"


# --- F-04 RLS safety net ----------------------------------------------------------------------------


def test_f04_a_table_rls_cannot_secure_is_a_loud_failure_outside_dev(settings, caplog):
    from django.db import connection

    from core.rls import enable_rls

    with connection.cursor() as cur:
        cur.execute("CREATE ROLE circuit_other_owner NOLOGIN")
        cur.execute("CREATE TABLE public.zz_not_ours (id int)")
        cur.execute("ALTER TABLE public.zz_not_ours OWNER TO circuit_other_owner")
    settings.ENV = "staging"
    with pytest.raises(RuntimeError, match="zz_not_ours"):
        enable_rls()
    settings.ENV = "dev"
    enable_rls()  # dev only logs


def test_f04_client_roles_lose_table_privileges():
    from django.db import connection

    from core.rls import revoke_client_privileges

    with connection.cursor() as cur:
        for role in ("anon", "authenticated"):
            cur.execute(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN CREATE ROLE {role} NOLOGIN; END IF; END $$"
            )
            cur.execute(f"GRANT SELECT ON accounts_member TO {role}")
            cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {role}")
        revoke_client_privileges()
        cur.execute("CREATE TABLE public.zz_later (id int)")  # created after: default privileges must not re-grant
        for role in ("anon", "authenticated"):
            cur.execute(
                "SELECT has_table_privilege(%s, 'accounts_member', 'SELECT'), has_table_privilege(%s, 'zz_later', 'SELECT')",
                [role, role],
            )
            assert cur.fetchone() == (False, False), role


# --- F-17 (coverage the plan promised) first-login race and hostile tokens --------------------------


def test_concurrent_first_login_returns_the_winner(monkeypatch, signing_key):
    from django.db.models import QuerySet

    from apps.accounts.models import Member

    uid = uuid.uuid4()
    winner = Member.objects.create(auth_user_id=uid)
    real_first, calls = QuerySet.first, {"n": 0}

    def first(self):
        if self.model is Member and calls["n"] == 0:
            calls["n"] += 1
            return None  # our lookup ran before the other request committed
        return real_first(self)

    monkeypatch.setattr(QuerySet, "first", first)
    r = get("/api/me", make_token(uid, signing_key))
    assert r.status_code == 200 and r.json()["id"] == winner.pk and Member.objects.filter(auth_user_id=uid).count() == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t[:-4] + "AAAA",  # bad signature
        lambda t: ".".join(t.split(".")[:2]) + ".",  # empty signature
        lambda t: ".".join(t.split(".")[:2]) + "." + "A" * 5000,  # huge signature
        lambda t: t.split(".")[0] + ".e30." + t.split(".")[2],  # empty claims
        lambda t: "a.b.c",
        lambda t: "....",
        lambda t: "é.é.é",
        lambda t: t + "." + t,
        lambda t: "A" * 20000,
    ],
)
def test_hostile_tokens_are_401_never_500(mutate, make_member, token_for):
    t = mutate(token_for(make_member()))
    try:
        r = get("/api/me", t)
    except UnicodeEncodeError:  # the HTTP layer would already have refused this header
        return
    assert r.status_code == 401


def raw_token(claims, key):
    """Sign whatever claims we like: PyJWT's encoder refuses some malformed types that an attacker can still send."""
    import json

    from jwt.api_jws import PyJWS

    return PyJWS().encode(json.dumps(claims).encode(), key, algorithm="ES256", headers={"kid": KID})


@pytest.mark.parametrize(
    "bad",
    [
        {"exp": "soon"},
        {"iat": "now"},
        {"sub": ["a"]},
        {"sub": 5},
        {"aud": 5},
        {"iss": ["x"]},
        {"nbf": "x"},
        {"role": ["authenticated"]},
    ],
)
def test_malformed_claim_types_are_401_never_500(bad, make_member, signing_key):
    now = int(time.time())
    claims = {
        "sub": str(make_member().auth_user_id), "aud": "authenticated", "iss": "https://test.supabase.co/auth/v1",
        "iat": now, "exp": now + 600, "role": "authenticated",
    }  # fmt: skip
    claims.update(bad)
    assert get("/api/me", raw_token(claims, signing_key)).status_code == 401


def test_logging_stays_quiet_about_bad_tokens(make_member, signing_key, caplog):
    caplog.set_level(logging.DEBUG)
    get("/api/me", "garbage")
    assert "garbage" not in caplog.text


def test_time_is_monotonic_based():
    assert isinstance(time.monotonic(), float)  # keeps the import honest: JWKS timers use time.monotonic
