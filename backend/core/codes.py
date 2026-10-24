"""One-time email codes (work-email check, startup claim). Only a hash is stored; the address is never stored or logged."""

import hashlib
import hmac
import re
import secrets

import structlog
from django.conf import settings
from django.core.mail import send_mail

from core.errors import ServiceUnavailable

log = structlog.get_logger("codes")

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L: codes get typed on phones
CODE_LENGTH = 8
MAX_ATTEMPTS = 5


# Deliberately narrow. The domain decides which organisation someone joins and whether they pass the beta gate, so we accept
# only plain ASCII addresses. Quoted strings, comments, encoded words, Unicode (the Kelvin sign lower-cases to a plain "k")
# and similar tricks are the ones mail systems read differently from us. Rejecting them only costs convenience.
_SIMPLE_EMAIL = re.compile(r"[a-z0-9][a-z0-9._+-]{0,63}@[a-z0-9-]+(?:\.[a-z0-9-]+)+")


def plain_email(email: str) -> str | None:
    """Lower-cased address if it is a plain ASCII address (see above), else None."""
    if not email.isascii():  # before lower(): the Kelvin sign lowercases to a plain "k" (audit F-06)
        return None
    email = email.lower()
    return email if len(email) <= 254 and _SIMPLE_EMAIL.fullmatch(email) else None


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def code_matches(code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_code(code), stored_hash)


def send_code(to_email: str, code: str, purpose: str) -> str | None:
    """Email the code. In dev and demo there is no real mailbox, so the code is also returned for the caller to show.

    Sent directly, not through the email outbox, on purpose: the outbox keeps the address and the text for a month, and a code
    email must leave nothing behind (the address is never stored). If the provider is down the caller gets a 503 and retries."""
    try:
        send_mail(f"Your Circuit code for {purpose}", f"Your code is {code}. It expires soon.", settings.EMAIL_FROM, [to_email])
    except Exception as exc:
        log.warning("code_email_failed", purpose=purpose, error=type(exc).__name__)
        raise ServiceUnavailable(
            "We couldn't send the email right now. Try again in a minute.", code="email_unavailable"
        ) from exc
    return code if settings.ENV in ("dev", "demo") else None


def email_domain(email: str) -> str:
    """Domain of a plain ASCII address, else ''. Same strictness as org auto-join (audit F-06)."""
    email = email.strip()
    if not email.isascii():  # before lower(): the Kelvin sign lowercases to a plain "k" (audit F-06)
        return ""
    email = email.lower()
    if email.count("@") != 1 or " " in email or '"' in email:
        return ""
    local, domain = email.split("@")
    return domain if local and "." in domain else ""
