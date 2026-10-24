"""Supabase Auth admin calls. The service-role key lives only in the backend; today the one call is deleting an auth user
when a member deletes their account.

Timeout and retries with backoff like every external call. A user that is already gone (404) counts as deleted, so running the
account deletion twice is safe. Without a Supabase project (dev, tests) nothing is called and the caller is told so.
"""

import time
import uuid
from collections.abc import Callable

import httpx
import structlog
from django.conf import settings

log = structlog.get_logger("supabase_admin")
TIMEOUT = 5.0
ATTEMPTS = 3

Deleter = Callable[[uuid.UUID], bool]
_deleter: Deleter | None = None


class AuthDeleteFailed(Exception):
    """Supabase did not confirm the deletion. The job leaves the account locked and tries again on its next run."""


def set_deleter(deleter: Deleter | None) -> None:
    """Tests install a fake here; None restores the real call."""
    global _deleter
    _deleter = deleter


def _delete_via_api(auth_user_id: uuid.UUID) -> bool:
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        log.warning("auth_user_not_deleted", reason="supabase not configured")
        return False  # dev: personas are not Supabase users
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{auth_user_id}"
    headers = {"apikey": settings.SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"}
    last = "no attempt"
    for attempt in range(ATTEMPTS):
        try:
            r = httpx.delete(url, headers=headers, timeout=TIMEOUT)
            if r.status_code < 300 or r.status_code == 404:
                return True
            if r.status_code < 500 and r.status_code != 429:
                raise AuthDeleteFailed(f"HTTP {r.status_code}")
            last = f"HTTP {r.status_code}"
        except httpx.HTTPError as exc:
            last = type(exc).__name__
        time.sleep(0.2 * 2**attempt)
    raise AuthDeleteFailed(last)


def delete_auth_user(auth_user_id: uuid.UUID) -> bool:
    """True if the user is gone from Supabase (deleted now, or already absent); False if there is no Supabase to call."""
    return (_deleter or _delete_via_api)(auth_user_id)
