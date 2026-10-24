"""Environment configuration, validated once at startup.

A missing or inconsistent variable raises here, so the app refuses to start
instead of failing later in a request.
"""

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent.parent


def _weak_secret(key: str) -> bool:
    lowered = key.lower()
    return (
        len(key) < 32
        or len(set(key)) < 10
        or any(marker in lowered for marker in ("change-me", "changeme", "django-insecure", "placeholder", "example"))
    )


def _check_preview_regex(pattern: str) -> None:
    """django-cors-headers uses re.match, which anchors the start only: the end must be anchored by us."""
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"CORS_PREVIEW_REGEX is not a valid regular expression: {exc}") from exc
    if not (pattern.startswith("^https://") and pattern.endswith("$") and not pattern.endswith("\\$")):
        raise ValueError("CORS_PREVIEW_REGEX must start with ^https:// and end with $ so it matches the whole origin")


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    env: Literal["dev", "demo", "staging", "production"]
    debug: bool = False
    secret_key: str = Field(min_length=16)
    database_url: str
    redis_url: str
    allowed_hosts: str
    cors_allowed_origins: str
    cors_preview_regex: str = ""
    csrf_trusted_origins: str = ""
    app_url: str
    landing_url: str
    api_url: str
    admin_path: str = "circuit-admin-x7k2/"
    demo_auth: bool = False
    demo_public: bool = False
    supabase_url: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_alg: Literal["ES256", "RS256"] = "ES256"
    supabase_service_role_key: str = ""  # backend only: storage uploads/signing and Realtime broadcasts
    storage_provider: Literal["local", "supabase"] = "local"
    llm_provider: Literal["gemini", "groq", "anthropic", "fake"] = "groq"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    embedding_provider: Literal["fastembed", "fake"] = "fastembed"
    email_backend: Literal["console", "disabled", "resend"] = "console"
    email_from: str = "Circuit <onboarding@resend.dev>"
    support_email: str = "support@example.com"
    resend_api_key: str = ""
    seed_city_name: str
    seed_city_lat: float
    seed_city_lng: float
    log_level: str = "INFO"
    features: str = ""  # default audience per flag, e.g. "pulse:everyone,circuits:testers" (PRODUCTION.md §2b)
    beta_mode: bool = False
    invites_per_member: int = Field(3, ge=0, le=50)  # beta invite codes each member can hand out (super admins change it here)
    trusted_proxy_hops: int = Field(0, ge=0, le=5)  # proxies in front of the API that append to X-Forwarded-For (Cloud Run: 1)
    razorpay_key_id: str = ""
    policy_version: str = Field(
        "2026-01", min_length=1, max_length=20
    )  # bump when the privacy policy or terms change: everyone re-accepts
    grievance_officer_name: str = (
        "<GRIEVANCE_OFFICER>"  # DPDP grievance contact; shown on the public contact endpoint and legal pages
    )
    grievance_email: str = "grievance@example.com"
    grievance_address: str = "<ADDRESS>"

    @model_validator(mode="after")
    def _check_env_rules(self) -> "Config":
        deployed = self.env in ("staging", "production")
        public = self.env != "dev"  # demo is internet-facing too, so it gets the same guard rails
        if deployed and self.demo_auth:
            raise ValueError("DEMO_AUTH must be false when ENV is staging or production")
        if self.demo_auth and self.env not in ("dev", "demo"):
            raise ValueError("DEMO_AUTH is only allowed in dev and demo")
        if public and self.debug:
            raise ValueError("DEBUG must be false outside dev")
        if deployed and not self.supabase_url:
            raise ValueError("SUPABASE_URL is required in staging and production")
        if self.supabase_url and public and not re.fullmatch(r"https://[^/\s]+", self.supabase_url.rstrip("/")):
            # The JWKS (the keys that decide who is signed in) is downloaded from here: it must be TLS.
            raise ValueError("SUPABASE_URL must be an https:// origin outside dev")
        if public and self.storage_provider == "supabase" and not (self.supabase_url and self.supabase_service_role_key):
            raise ValueError("STORAGE_PROVIDER=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        if deployed and self.storage_provider != "supabase":
            raise ValueError("STORAGE_PROVIDER must be supabase in staging and production (local files are for dev)")
        if deployed and self.llm_provider == "fake":
            raise ValueError("LLM_PROVIDER=fake is only for tests")
        if public and _weak_secret(self.secret_key):
            raise ValueError(
                "SECRET_KEY looks weak or like a placeholder (need 32+ chars, 10+ distinct, not 'change-me'/'django-insecure'). "
                "Demo tokens and sessions are signed with it."
            )
        if public and "*" in self.csv(self.allowed_hosts):
            raise ValueError("ALLOWED_HOSTS must not contain '*' outside dev")
        if public and any(not re.fullmatch(r"https?://[^/\s*]+", o) for o in self.csv(self.cors_allowed_origins)):
            raise ValueError("CORS_ALLOWED_ORIGINS must be exact origins like https://app.example (no path, slash or wildcard)")
        if self.cors_preview_regex:
            if self.env not in ("dev", "staging"):
                raise ValueError("CORS_PREVIEW_REGEX is for staging only and must be empty elsewhere")
            _check_preview_regex(self.cors_preview_regex)
        self._check_flags()
        self._check_beta_and_email()
        return self

    def _check_flags(self) -> None:
        from core.flags import check_dependencies, parse_features

        audiences = parse_features(self.features)
        check_dependencies(audiences)
        live_key = self.razorpay_key_id.startswith("rzp_live_")
        if live_key and self.env != "production":
            raise ValueError("Razorpay live keys are only allowed when ENV is production")
        if self.env == "production" and audiences["payments"] != "off" and not live_key:
            raise ValueError("payments is on in production: RAZORPAY_KEY_ID must be a live key (rzp_live_...)")

    def _check_beta_and_email(self) -> None:
        if self.env in ("staging", "production") and self.trusted_proxy_hops < 1:
            # Per-IP limits (waitlist, redeem) read the client address from X-Forwarded-For. With no trusted proxy configured
            # every visitor would share the load balancer's address and one abuser would lock everyone out.
            raise ValueError("TRUSTED_PROXY_HOPS must be at least 1 in staging and production (Cloud Run is one hop)")
        if self.email_backend == "resend" and not self.resend_api_key:
            raise ValueError("EMAIL_BACKEND=resend needs RESEND_API_KEY")
        if self.env == "production" and "@resend.dev" in self.email_from:
            raise ValueError("EMAIL_FROM is still Resend's test sender; verify the domain and set EMAIL_FROM in production")

    def csv(self, value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]


def load_config() -> Config:
    return Config()  # type: ignore[call-arg]
