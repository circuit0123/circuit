import base64
import hashlib
import hmac
import json
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from django.test import Client

from core import auth
from tests.conftest import ISSUER, KID, make_token

pytestmark = pytest.mark.django_db


def get_me(token=None, **headers):
    h = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return Client().get("/api/me", **h, **headers)


def test_valid_token_returns_member(make_member, token_for):
    m = make_member("founder")
    r = get_me(token_for(m))
    assert r.status_code == 200 and r.json()["id"] == m.pk and r.json()["role"] == "founder"


def test_missing_token_is_401_in_standard_format():
    r = get_me()
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer not.a.jwt", "bearer "])
def test_garbage_authorization_is_401(header):
    assert Client().get("/api/me", HTTP_AUTHORIZATION=header).status_code == 401


def test_expired_token_rejected(make_member, signing_key):
    m = make_member()
    t = make_token(m.auth_user_id, signing_key, exp=int(time.time()) - 3600, iat=int(time.time()) - 7200)
    assert get_me(t).status_code == 401


def test_not_yet_valid_token_rejected(make_member, signing_key):
    m = make_member()
    t = make_token(m.auth_user_id, signing_key, iat=int(time.time()) + 3600, nbf=int(time.time()) + 3600)
    assert get_me(t).status_code == 401


def test_forged_signature_rejected(make_member, other_key):
    m = make_member()
    assert get_me(make_token(m.auth_user_id, other_key)).status_code == 401


@pytest.mark.parametrize(
    "claims", [{"aud": "someone-else"}, {"iss": "https://evil.example/auth/v1"}, {"role": "anon"}, {"is_anonymous": True}]
)
def test_wrong_claims_rejected(make_member, signing_key, claims):
    m = make_member()
    assert get_me(make_token(m.auth_user_id, signing_key, **claims)).status_code == 401


@pytest.mark.parametrize("missing", ["exp", "iat", "aud", "iss", "sub"])
def test_required_claims(make_member, signing_key, missing):
    m = make_member()
    token = make_token(None, signing_key) if missing == "sub" else make_token(m.auth_user_id, signing_key, **{missing: None})
    assert get_me(token).status_code == 401


def test_alg_none_rejected(make_member):
    m = make_member()
    t = jwt.encode(
        {"sub": str(m.auth_user_id), "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 600}, None, algorithm="none"
    )
    assert get_me(t).status_code == 401


def test_hs256_signed_with_public_key_rejected(make_member, signing_key):
    """Classic algorithm confusion: attacker signs HS256 using the (public) verification key as the secret."""
    m = make_member()
    pub_pem = signing_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    now = int(time.time())
    claims = {
        "sub": str(m.auth_user_id),
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 600,
        "role": "authenticated",
    }

    def b64(obj) -> bytes:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=")

    signing_input = b64({"alg": "HS256", "typ": "JWT", "kid": KID}) + b"." + b64(claims)
    sig = base64.urlsafe_b64encode(hmac.new(pub_pem, signing_input, hashlib.sha256).digest()).rstrip(b"=")
    t = (signing_input + b"." + sig).decode()
    assert get_me(t).status_code == 401


def test_non_uuid_subject_rejected(signing_key):
    assert get_me(make_token("not-a-uuid", signing_key)).status_code == 401


def test_unknown_kid_rejected_and_refetch_throttled(make_member, signing_key, supabase):
    m = make_member()
    assert get_me(make_token(m.auth_user_id, signing_key)).status_code == 200  # loads the key set
    before = supabase["n"]
    for i in range(5):  # a flood of random kids
        assert get_me(make_token(m.auth_user_id, signing_key, kid=f"rand-{i}")).status_code == 401
    assert supabase["n"] - before <= 1  # at most one refetch inside the throttle window


def test_jwks_down_without_keys_is_503(make_member, signing_key, supabase):
    supabase["down"] = True
    r = get_me(make_token(make_member().auth_user_id, signing_key))
    assert r.status_code == 503 and r.json()["error"]["code"] == "auth_unavailable"


def test_jwks_down_serves_stale_keys(make_member, signing_key, supabase, monkeypatch):
    m = make_member()
    assert get_me(make_token(m.auth_user_id, signing_key)).status_code == 200
    supabase["down"] = True
    auth._state.fetched_at -= auth.JWKS_TTL + 1  # cache expired
    auth._state.last_attempt -= auth.REFETCH_AFTER_KEYS + 1
    assert get_me(make_token(m.auth_user_id, signing_key)).status_code == 200


def test_first_login_creates_student_member(signing_key):
    from apps.accounts.models import Member

    uid = uuid.uuid4()
    r = get_me(make_token(uid, signing_key))
    assert r.status_code == 200 and r.json()["role"] == "student"
    m = Member.objects.get(auth_user_id=uid)
    assert m.verification_level == 1 and m.display_name == ""
    assert get_me(make_token(uid, signing_key)).json()["id"] == m.pk  # second login: same member
    assert Member.objects.filter(auth_user_id=uid).count() == 1


def test_first_login_event_has_no_pii(signing_key):
    from apps.events.models import Event

    get_me(make_token(uuid.uuid4(), signing_key, email="private.person@kit.edu.in"))
    e = Event.objects.get(type="member.created")
    assert "private" not in str(e.payload) and "kit.edu.in" not in str(e.payload)


def test_first_login_auto_joins_org_on_verified_domain(signing_key, make_org):
    from apps.accounts.models import Member

    org = make_org(domains=["kit.edu.in"])
    uid = uuid.uuid4()
    get_me(make_token(uid, signing_key, email="Asha@KIT.edu.in"))
    assert Member.objects.get(auth_user_id=uid).organisation_id == org.pk


@pytest.mark.parametrize("provider", ["phone", "github", None])
def test_unverified_provider_does_not_auto_join(signing_key, make_org, provider):
    from apps.accounts.models import Member

    make_org(domains=["kit.edu.in"])
    uid = uuid.uuid4()
    get_me(make_token(uid, signing_key, email="a@kit.edu.in", app_metadata={"provider": provider} if provider else {}))
    assert Member.objects.get(auth_user_id=uid).organisation_id is None


def test_user_metadata_cannot_fake_verification(signing_key, make_org):
    from apps.accounts.models import Member

    make_org(domains=["kit.edu.in"])
    uid = uuid.uuid4()
    t = make_token(uid, signing_key, email=None, user_metadata={"email": "a@kit.edu.in", "email_verified": True})
    get_me(t)
    assert Member.objects.get(auth_user_id=uid).organisation_id is None


def test_request_log_carries_member_id_only(make_member, token_for, capfd):
    m = make_member(display_name="Secret Name")
    get_me(token_for(m, email="leak@example.org"))
    out = capfd.readouterr().out
    line = next(json.loads(x) for x in out.splitlines() if '"request"' in x)
    assert line["member_id"] == m.pk
    assert "leak@example.org" not in out and "Secret Name" not in out


# --- demo tokens ---------------------------------------------------------------------------------


@pytest.fixture
def demo_on(settings):
    settings.DEMO_AUTH = True
    settings.ENV = "dev"


def demo_token(member):
    return auth.issue_demo_token(member.auth_user_id)


def test_demo_token_works_when_demo_auth_on(demo_on, make_member):
    m = make_member("founder")
    assert get_me(demo_token(m)).status_code == 200


def test_demo_token_rejected_when_demo_auth_off(demo_on, make_member, settings):
    m = make_member()
    t = demo_token(m)
    settings.DEMO_AUTH = False
    assert get_me(t).status_code == 401


def test_demo_token_never_creates_members(demo_on):
    from apps.accounts.models import Member

    t = auth.issue_demo_token(uuid.uuid4())
    assert get_me(t).status_code == 401 and Member.objects.count() == 0


def test_demo_token_signed_with_other_secret_rejected(demo_on, make_member):
    m = make_member()
    now = int(time.time())
    forged = jwt.encode(
        {"sub": str(m.auth_user_id), "iss": auth.DEMO_ISSUER, "aud": auth.DEMO_AUDIENCE, "iat": now, "exp": now + 600},
        "x" * 32, algorithm="HS256",
    )  # fmt: skip
    assert get_me(forged).status_code == 401


def test_demo_token_with_wrong_audience_rejected(demo_on, make_member, settings):
    m = make_member()
    now = int(time.time())
    t = jwt.encode(
        {"sub": str(m.auth_user_id), "iss": auth.DEMO_ISSUER, "aud": "authenticated", "iat": now, "exp": now + 600},
        auth._demo_key(), algorithm="HS256",
    )  # fmt: skip
    assert get_me(t).status_code == 401


def test_issuing_demo_token_impossible_when_off(make_member):
    with pytest.raises(RuntimeError):
        auth.issue_demo_token(make_member().auth_user_id)


def test_supabase_token_not_accepted_as_demo(demo_on, make_member, signing_key):
    """Demo and Supabase paths are separate: a Supabase-shaped token never takes the demo path."""
    m = make_member()
    assert get_me(make_token(m.auth_user_id, signing_key)).status_code == 200  # via the Supabase path, fully verified
    assert get_me(make_token(m.auth_user_id, signing_key, aud="circuit-demo", iss=auth.DEMO_ISSUER)).status_code == 401
