"""One-time email codes (work-email check, startup claim). Only a hash is stored; the address is never stored or logged."""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.mail import send_mail

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L: codes get typed on phones
CODE_LENGTH = 8
MAX_ATTEMPTS = 5


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def code_matches(code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_code(code), stored_hash)


def send_code(to_email: str, code: str, purpose: str) -> str | None:
    """Email the code. In dev and demo there is no real mailbox, so the code is also returned for the caller to show."""
    send_mail(f"Your Circuit code for {purpose}", f"Your code is {code}. It expires soon.", settings.EMAIL_FROM, [to_email])
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
