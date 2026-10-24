"""Authentication: who is calling?

Two token kinds, never mixed:
- Supabase JWTs (staging/production, and any env with SUPABASE_URL): asymmetric
  signature checked against Supabase's JWKS, with the algorithm pinned by config.
- Demo tokens (DEMO_AUTH only, dev/demo): HS256 signed with a key derived from
  SECRET_KEY, a different issuer and audience, and they only ever map to seeded personas.

`SupabaseAuth` is the API-wide default (circuit/api.py), so an endpoint is protected
unless it opts out with `auth=None`. The result is an `AuthContext` on `request.auth`.
"""

import hashlib
import hmac
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import jwt
import structlog
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from ninja.security import HttpBearer

from core.codes import plain_email
from core.errors import AccountSuspended, ServiceUnavailable

log = structlog.get_logger("auth")

DEMO_ISSUER = "circuit-demo"
DEMO_AUDIENCE = "circuit-demo"
DEMO_ALG = "HS256"
DEMO_TOKEN_TTL = 12 * 3600
LEEWAY_SECONDS = 10

JWKS_TIMEOUT = 3.0
JWKS_ATTEMPTS = 3
JWKS_TTL = 600  # re-read the key set at most this often
JWKS_MAX_STALE = 6 * 3600  # if Supabase stays unreachable this long, stop trusting the old keys (a rotated key must die)
REFETCH_AFTER_KEYS = 60  # throttle for unknown-kid refetches while we hold keys
REFETCH_AFTER_NONE = 5  # throttle while we hold none (Supabase was unreachable)
REACHABLE_CACHE_SECONDS = 15  # /api/health/deps is public: it must not become a free way to call Supabase

# Sign-in providers that prove control of the mailbox. Only these may auto-join an organisation.
# `app_metadata` is writable only by Supabase; `user_metadata` is user-editable, so never read it.
VERIFIED_EMAIL_PROVIDERS = {"google", "email"}
ASYMMETRIC_KTY = {"ES256": "EC", "RS256": "RSA"}


@dataclass(frozen=True)
class AuthContext:
    member: Any  # apps.accounts.models.Member
    verified_email: str | None  # in memory only; never stored or logged
    kind: Literal["supabase", "demo"]


# --- demo tokens ---------------------------------------------------------------------------------


def _demo_key() -> bytes:
    return hmac.new(settings.SECRET_KEY.encode(), b"circuit-demo-auth-v1", hashlib.sha256).digest()


def issue_demo_token(auth_user_id: uuid.UUID) -> str:
    """Only called by core/demo.py, which refuses unless DEMO_AUTH is on."""
    if not settings.DEMO_AUTH:
        raise RuntimeError("DEMO_AUTH is off")
    now = int(time.time())
    claims = {"sub": str(auth_user_id), "iss": DEMO_ISSUER, "aud": DEMO_AUDIENCE, "iat": now, "exp": now + DEMO_TOKEN_TTL}
    return jwt.encode(claims, _demo_key(), algorithm=DEMO_ALG)


def _decode_demo(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            _demo_key(),
            algorithms=[DEMO_ALG],
            audience=DEMO_AUDIENCE,
            issuer=DEMO_ISSUER,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError:
        return None


# --- Supabase JWKS -------------------------------------------------------------------------------


class _KeyState:
    """Immutable-by-convention snapshot: refreshes publish a new object instead of mutating this one."""

    def __init__(self, keys: dict[str, Any] | None = None, fetched_at: float = 0.0, last_attempt: float = float("-inf")) -> None:
        self.keys = keys or {}
        self.fetched_at = fetched_at
        self.last_attempt = last_attempt


_state = _KeyState()
_refresh_lock = threading.Lock()  # serialises downloads only; reading keys never takes it
_reachable: tuple[float, bool] | None = None


def jwks_url() -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"


def issuer() -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"


def _fetch_jwks(attempts: int = JWKS_ATTEMPTS, timeout: float = JWKS_TIMEOUT) -> dict[str, Any]:
    """Download the key set. Timeout + retries with backoff; raises if every attempt fails."""
    want_kty = ASYMMETRIC_KTY[settings.SUPABASE_JWT_ALG]
    last: Exception | None = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(0.2 * 3**attempt)
        try:
            resp = httpx.get(jwks_url(), timeout=timeout)
            resp.raise_for_status()
            keys: dict[str, Any] = {}
            for jwk in resp.json().get("keys", []):
                # Only keys of the pinned family: an HMAC "oct" key here would enable algorithm confusion.
                if isinstance(jwk, dict) and jwk.get("kid") and jwk.get("kty") == want_kty:
                    keys[jwk["kid"]] = jwt.PyJWK(jwk).key
            return keys
        except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
            last = exc
    raise last or RuntimeError("jwks fetch failed")


def _refresh_keys() -> None:
    """Download the key set. Called with _refresh_lock held, and never while a request holds any other lock."""
    global _state
    now = time.monotonic()
    old = _state
    if now - old.last_attempt < (REFETCH_AFTER_KEYS if old.keys else REFETCH_AFTER_NONE):
        return  # another request just tried
    # Publish the attempt time first, so requests arriving during the slow download use the keys we have.
    _state = _KeyState(old.keys, old.fetched_at, now)
    try:
        keys = _fetch_jwks()
    except Exception as exc:
        log.warning("jwks_fetch_failed", error=type(exc).__name__, serving_stale=bool(old.keys))
        return
    _state = _KeyState(keys, now, now)


def _signing_key(kid: str) -> Any | None:
    """Key for `kid`, or None if Supabase doesn't publish it. Raises ServiceUnavailable if we hold no usable keys."""
    state = _state
    now = time.monotonic()
    key = state.keys.get(kid)
    if key is not None and now - state.fetched_at < JWKS_TTL:
        return key
    # Cache expired, or an unknown kid. Refetch, but throttled, so random kids can't make us hammer Supabase.
    if now - state.last_attempt >= (REFETCH_AFTER_KEYS if state.keys else REFETCH_AFTER_NONE):
        # With keys in hand, a request never waits for someone else's download; with none, it must.
        if _refresh_lock.acquire(blocking=not state.keys):
            try:
                _refresh_keys()
            finally:
                _refresh_lock.release()
    state = _state
    if not state.keys or time.monotonic() - state.fetched_at > JWKS_MAX_STALE:
        raise ServiceUnavailable("Sign-in is temporarily unavailable", code="auth_unavailable")
    return state.keys.get(kid)


def reset_jwks_cache() -> None:
    """Tests (and a key-rotation emergency) clear the cache here."""
    global _state, _reachable
    _state = _KeyState()
    _reachable = None


def jwks_reachable() -> bool:
    """For /api/health/deps. Public endpoint, so the answer is cached instead of calling Supabase every time."""
    global _reachable
    now = time.monotonic()
    if _reachable and now - _reachable[0] < REACHABLE_CACHE_SECONDS:
        return _reachable[1]
    try:
        ok = bool(_fetch_jwks(attempts=1, timeout=2.0))
    except Exception:
        ok = False
    _reachable = (now, ok)
    return ok


def _decode_supabase(token: str) -> dict | None:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        return None
    kid = header.get("kid")
    if header.get("alg") != settings.SUPABASE_JWT_ALG or not isinstance(kid, str):
        return None
    key = _signing_key(kid)
    if key is None:
        return None
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[settings.SUPABASE_JWT_ALG],
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=issuer(),
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("role") != "authenticated" or claims.get("is_anonymous"):
        return None
    return claims


def _verified_email(claims: dict) -> str | None:
    email = claims.get("email")
    provider = (claims.get("app_metadata") or {}).get("provider")
    if not isinstance(email, str) or provider not in VERIFIED_EMAIL_PROVIDERS:
        return None
    return plain_email(email)


# --- members -------------------------------------------------------------------------------------


def _member_for_supabase(auth_user_id: uuid.UUID, verified_email: str | None):
    from apps.accounts.models import Member
    from apps.events.services import record

    member = Member.objects.filter(auth_user_id=auth_user_id).first()
    if member:
        return member
    try:
        with transaction.atomic():
            member = Member.objects.create(auth_user_id=auth_user_id)
    except IntegrityError:  # a parallel first request created it
        return Member.objects.get(auth_user_id=auth_user_id)
    record("member.created", actor=member, target_type="member", target_id=member.pk)
    if verified_email:
        from apps.organisations.services import join_by_email

        join_by_email(member, verified_email, quiet=True)
    return member


def _member_for_demo(auth_user_id: uuid.UUID):
    from apps.accounts.models import Member

    return Member.objects.filter(auth_user_id=auth_user_id).first()  # demo tokens never create members


class SupabaseAuth(HttpBearer):
    """API-wide default auth. Returns None (401) for anything that is not a valid token for a known member.

    The invite-only beta gate (F18) lives here and nowhere else: every protected endpoint passes through `authenticate`,
    so a new endpoint is gated without its author doing anything. Public endpoints that peek at the caller use `identify`.
    """

    def authenticate(self, request: HttpRequest, token: str) -> AuthContext | None:
        ctx = self.identify(request, token)
        if ctx is not None and settings.BETA_MODE:
            from apps.beta import gate

            gate.enforce(request, ctx)
        return ctx

    def identify(self, request: HttpRequest, token: str) -> AuthContext | None:
        """Who is calling, with no access gate. Raises AccountSuspended for a suspended member."""
        try:
            alg = jwt.get_unverified_header(token).get("alg")
        except jwt.PyJWTError:
            return None
        if settings.DEMO_AUTH and alg == DEMO_ALG:
            claims, kind = _decode_demo(token), "demo"
        elif alg == settings.SUPABASE_JWT_ALG and settings.SUPABASE_URL:
            claims, kind = _decode_supabase(token), "supabase"
        else:
            return None
        if claims is None:
            return None
        try:
            auth_user_id = uuid.UUID(str(claims["sub"]))
        except ValueError:
            return None

        if kind == "demo":
            member, email = _member_for_demo(auth_user_id), None
        else:
            email = _verified_email(claims)
            member = _member_for_supabase(auth_user_id, email)
        if member is None:
            return None
        if member.suspended_at is not None:
            # Checked on every request against the database, so a suspension bites at once, not when the token expires.
            raise AccountSuspended()
        request.member_id = member.pk  # type: ignore[attr-defined]  # picked up by the request log line
        return AuthContext(member=member, verified_email=email, kind=kind)  # type: ignore[arg-type]


def current_member(request: HttpRequest):
    """The authenticated Member. Only valid on endpoints that did not opt out of auth."""
    return request.auth.member  # type: ignore[attr-defined]


def current_context(request: HttpRequest) -> AuthContext:
    return request.auth  # type: ignore[attr-defined]
