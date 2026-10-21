import json
import time
import uuid

import fakeredis
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import Client

from core import auth, cache, embeddings, llm

SUPABASE_URL = "https://test.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
KID = "test-key-1"


@pytest.fixture(autouse=True)
def fakes():
    """No live network in tests: fake Redis, fake embeddings, mocked LLM."""
    cache.set_cache(cache.Cache(fakeredis.FakeRedis()))
    embeddings.set_embedder(embeddings.FakeEmbeddingProvider())
    fake = llm.FakeLLM()
    llm.set_llm(fake)
    yield fake
    cache.set_cache(None)
    embeddings.set_embedder(None)
    llm.set_llm(None)


@pytest.fixture
def fake_llm(fakes):
    return fakes


@pytest.fixture(scope="session")
def signing_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def other_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(autouse=True)
def supabase(settings, signing_key, monkeypatch):
    """Point auth at a fake Supabase whose JWKS is our test key. No network."""
    settings.SUPABASE_URL = SUPABASE_URL
    settings.SUPABASE_JWT_ALG = "ES256"
    settings.SUPABASE_JWT_AUDIENCE = "authenticated"
    settings.DEMO_AUTH = False
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update(kid=KID, alg="ES256", use="sig")
    calls = {"n": 0, "down": False}

    def fake_fetch(attempts=1, timeout=1.0):
        calls["n"] += 1
        if calls["down"]:
            raise ConnectionError("supabase down")
        return {KID: jwt.PyJWK(jwk).key}

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)
    auth.reset_jwks_cache()
    yield calls
    auth.reset_jwks_cache()


def make_token(subject, key, kid=KID, alg="ES256", **over):
    now = int(time.time())
    claims = {
        "sub": str(subject) if subject is not None else None, "aud": "authenticated", "iss": ISSUER, "iat": now, "exp": now + 3600,
        "role": "authenticated", "email": "someone@example.org", "app_metadata": {"provider": "google"},
    }  # fmt: skip
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


@pytest.fixture
def make_member(db):
    from apps.accounts.models import Member

    def _make(role="student", org=None, level=1, visible_to_org=False, **kw):
        return Member.objects.create(
            auth_user_id=kw.pop("auth_user_id", None) or uuid.uuid4(), role=role, organisation=org, verification_level=level,
            visible_to_org=visible_to_org, display_name=kw.pop("display_name", f"Test {role}"), **kw,
        )  # fmt: skip

    return _make


@pytest.fixture
def make_org(db):
    from apps.organisations.models import Organisation

    def _make(name="Test College", domains=None, code=None):
        return Organisation.objects.create(
            name=name,
            kind="college",
            city="Chennai",
            email_domains=domains or [],
            join_code=code or uuid.uuid4().hex[:10].upper(),
        )

    return _make


@pytest.fixture
def token_for(signing_key):
    def _token(member, **claims):
        return make_token(member.auth_user_id, signing_key, **claims)

    return _token


@pytest.fixture
def client_for(token_for):
    """A test client that sends a valid Supabase token for `member`. No member -> anonymous."""

    class AuthedClient(Client):
        def __init__(self, member=None, **claims):
            extra = {"HTTP_AUTHORIZATION": f"Bearer {token_for(member, **claims)}"} if member else {}
            super().__init__(**extra)

        # Django's client defaults to multipart; our API speaks JSON.
        def post(self, path, data=None, content_type="application/json", **extra):
            return super().post(path, data, content_type=content_type, **extra)

        def put(self, path, data="", content_type="application/json", **extra):
            return super().put(path, data, content_type=content_type, **extra)

        def patch(self, path, data="", content_type="application/json", **extra):
            return super().patch(path, data, content_type=content_type, **extra)

    return AuthedClient
