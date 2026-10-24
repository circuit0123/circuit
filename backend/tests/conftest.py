import json
import time
import uuid

import fakeredis
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import Client

from core import auth, cache, embeddings, flags, llm, storage

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
    storage.set_storage(storage.MemoryStorage())
    from apps.messaging import realtime

    realtime.set_sender(lambda topic, event, payload: None)
    yield fake
    storage.set_storage(None)
    realtime.set_sender(None)
    cache.set_cache(None)
    embeddings.set_embedder(None)
    llm.set_llm(None)


@pytest.fixture(autouse=True)
def all_flags_on(settings):
    """Every feature is on unless a test switches one off. Flag tests set settings.FEATURES themselves."""
    settings.FEATURES = ",".join(f"{name}:everyone" for name in flags.FLAGS)


@pytest.fixture(autouse=True)
def beta_off(settings):
    """The invite-only beta is off unless a test switches it on (the `beta_on` fixture); the dev .env must not leak in."""
    settings.BETA_MODE = False
    settings.TRUSTED_PROXY_HOPS = 0
    settings.INVITES_PER_MEMBER = 3


@pytest.fixture
def beta_on(settings):
    settings.BETA_MODE = True


@pytest.fixture(autouse=True)
def consent_ok(request, monkeypatch, settings):
    """Test members have not clicked through the consent screen; the consent gate is off unless a test uses `consent_on`."""
    settings.POLICY_VERSION = "2026-01"
    if "consent_on" not in request.fixturenames:
        from core import gate

        monkeypatch.setattr(gate, "needs_consent", lambda member: False)


@pytest.fixture
def consent_on():
    """Marker: run this test with the real consent gate (members need a Consent row for the current POLICY_VERSION)."""


@pytest.fixture(autouse=True)
def auth_deletions():
    """No call to Supabase's admin API: account deletion records the auth user ids it was asked to delete."""
    from core import supabase_admin

    deleted: list = []
    supabase_admin.set_deleter(lambda auth_user_id: deleted.append(auth_user_id) or True)
    yield deleted
    supabase_admin.set_deleter(None)


@pytest.fixture
def realtime_events():
    """Everything broadcast over Realtime during the test, as (topic, event, payload)."""
    from core import realtime

    sent: list = []
    realtime.set_sender(lambda topic, event, payload: sent.append((topic, event, payload)))
    return sent


@pytest.fixture
def let_in(db):
    """Give a member beta access the way a redeemed code would."""
    from apps.beta.models import BetaAccess

    return lambda member, source="code": BetaAccess.objects.create(member=member, source=source)


@pytest.fixture
def make_code(db):
    from apps.beta import services

    def _make(**kw):
        return services.create_code(**kw)

    return _make


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


@pytest.fixture
def lists(db):
    """The fixed capability and trait lists (seed tests load them too)."""
    from apps.matching.lists import sync_lists
    from apps.matching.models import Capability, Trait

    sync_lists(Capability, Trait)


@pytest.fixture
def make_startup(db):
    from django.contrib.gis.geos import Point

    from apps.startups.models import Startup

    def _make(name="Acme", domain="acme.io", lat=13.08, lng=80.27, hiring=False, claimed_by=None, **kw):
        return Startup.objects.create(
            name=name, website_domain=domain, location=Point(lng, lat, srid=4326), hiring=hiring, claimed_by=claimed_by, **kw
        )

    return _make


@pytest.fixture
def connect(db):
    from apps.accounts.models import Connection

    def _connect(a, b):
        x, y = sorted((a.pk, b.pk))
        return Connection.objects.create(member_a_id=x, member_b_id=y, strength=0.5)

    return _connect


@pytest.fixture
def block(db):
    from apps.moderation.models import Block

    return lambda blocker, blocked: Block.objects.create(blocker=blocker, blocked=blocked)


@pytest.fixture
def make_post(db):
    from apps.social.models import Post

    def _post(author, visibility="everyone", body="Shipped the login screen", **kw):
        return Post.objects.create(author=author, body=body, visibility=visibility, **kw)

    return _post


@pytest.fixture
def make_image():
    """Real PNG/JPEG bytes (optionally with EXIF GPS) for upload tests."""
    import io

    from PIL import Image

    def _image(fmt="PNG", size=(64, 48), exif=False) -> bytes:
        img = Image.new("RGB", size, (200, 80, 40))
        buf = io.BytesIO()
        kw = {}
        if exif:
            e = Image.Exif()
            e[0x010F] = "TestCam"  # Make
            e[0x8825] = {1: "N", 2: (13.0, 5.0, 0.0)}  # GPS block
            kw["exif"] = e
        img.save(buf, fmt, **kw)
        return buf.getvalue()

    return _image


# -- demo stories: `make check` prints PASS/FAIL per story ------------------------------------------------------------
STORY_NAMES = {
    1: "Biotech needs marketing, matched to a deep-tech marketer (Bridge match)",
    2: "Exchange circuit: Asha, Priya and Arjun",
    3: "Tier-3 student applies and is the founder's top applicant",
    4: "Warm intro through a respected mentor",
    5: "Regulatory-help gap on the partner dashboard",
}
_story_outcomes: dict[int, str] = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "story(n): this test belongs to demo story n (see STORY_NAMES in tests/conftest.py)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    marker = item.get_closest_marker("story")
    if marker is None:
        return
    n = marker.args[0]
    if report.failed:
        _story_outcomes[n] = "FAIL"
    elif report.when == "call" and report.passed:
        _story_outcomes.setdefault(n, "PASS")


def pytest_terminal_summary(terminalreporter):
    """One line per story, so a failing story is obvious without reading the test names."""
    if not _story_outcomes:
        return  # a partial run that did not touch the stories
    terminalreporter.section("demo stories")
    for n, name in STORY_NAMES.items():
        result = _story_outcomes.get(n, "NOT RUN")
        terminalreporter.write_line(f"Story {n}: {result}  {name}", red=result != "PASS", green=result == "PASS")


@pytest.fixture
def staff_request(rf):
    """A fake Django admin request from a staff superuser, for calling admin actions directly. Returns (request, staff user)."""
    from django.contrib.auth import get_user_model
    from django.contrib.messages.storage.cookie import CookieStorage

    staff = get_user_model().objects.create_superuser("mod", password="a-long-test-password-1")
    request = rf.post("/")
    request.user = staff
    request._messages = CookieStorage(request)
    return request, staff
