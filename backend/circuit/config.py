"""Environment configuration, validated once at startup.

A missing or inconsistent variable raises here, so the app refuses to start
instead of failing later in a request.
"""

import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

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


def parse_job_intervals(text: str) -> dict[str, int]:
    """'compute_matches:1440,expire_items:5' -> {...}. A malformed entry raises: a typo would silently switch a job's alert off."""
    out: dict[str, int] = {}
    for part in (p.strip() for p in text.split(",") if p.strip()):
        name, _, minutes = part.partition(":")
        if not name or not minutes.isdigit() or int(minutes) < 1:
            raise ValueError(f"JOB_INTERVALS entry '{part}' must look like name:minutes")
        out[name] = int(minutes)
    return out


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
    database_url: str = Field(min_length=1)
    redis_url: str = ""  # empty = no Redis at all: cache reads miss and rate limits count in Postgres (the "Redis is down" path)
    media_webp_quality: int = Field(
        82, ge=40, le=95
    )  # first-try quality of uploaded images; 75 saves a fifth of the storage (free plan: 1 GB)
    redis_lean: bool = (
        False  # true on Upstash's free plan: keep fewer copies in Redis (core/cache). Production, staging and demo set it
    )
    redis_lean_max_ttl: int = Field(600, ge=1)  # seconds an essential entry may live in lean mode
    database_pooler: Literal["direct", "transaction"] = (
        "direct"  # "transaction" = Supabase's transaction pooler (port 6543), PRODUCTION.md "Database connections"
    )
    allowed_hosts: str = Field(min_length=1)
    cors_allowed_origins: str = Field(min_length=1)
    cors_preview_regex: str = ""
    csrf_trusted_origins: str = ""
    app_url: str = Field(min_length=1)
    landing_url: str = Field(min_length=1)
    api_url: str = Field(min_length=1)
    admin_path: str = "circuit-admin-x7k2/"
    demo_auth: bool = False
    demo_public: bool = False
    supabase_url: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_alg: Literal["ES256", "RS256"] = "ES256"
    supabase_service_role_key: str = ""  # backend only: storage uploads/signing and Realtime broadcasts
    storage_provider: Literal["local", "supabase"] = "local"
    llm_provider: Literal["gemini", "groq", "anthropic", "none", "fake"] = "groq"  # none = manual pickers only, no LLM at all
    llm_daily_call_limit: int = Field(
        0, ge=0
    )  # provider calls per India day, all instances together; past it onboarding uses the manual pickers. 0 = no cap
    gemini_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    embedding_provider: Literal["fastembed", "fake"] = "fastembed"
    email_backend: Literal["console", "disabled", "resend"] = "console"
    email_from: str = "Circuit <onboarding@resend.dev>"
    support_email: str = "support@example.com"
    resend_api_key: str = ""
    # Resend free plan: 100 a day, 3,000 a month. The BUDGETS stop optional notification emails a little before the LIMITS, which are the
    # provider's own ceilings (core/email.py). 0 = no limit: set all four to 0 on a paid plan.
    email_daily_budget: int = Field(90, ge=0)
    email_monthly_budget: int = Field(2800, ge=0)
    email_daily_limit: int = Field(100, ge=0)
    email_monthly_limit: int = Field(3000, ge=0)
    seed_city_name: str = Field(min_length=1)
    seed_city_lat: float
    seed_city_lng: float
    log_level: str = "INFO"
    sentry_dsn: str = ""  # empty = Sentry off (dev, tests). A secret in production: it identifies our project
    sentry_traces_sample_rate: float = Field(0.0, ge=0, le=1)  # performance traces; 0 keeps us inside Sentry's free quota
    backup_bucket: str = ""  # private bucket for the nightly encrypted dump; empty = write to backend/.backups/ (a laptop)
    backup_database_url: str = (
        ""  # secret: the Supabase SESSION pooler (or direct) address; pg_dump cannot use the transaction pooler
    )
    backup_age_recipient: str = ""  # the age PUBLIC key the dump is encrypted to. The private key stays offline
    free_tier_limits: str = (
        ""  # JSON object overriding FREE_TIER_LIMITS (settings.py) on a paid plan, e.g. {"database_bytes": 8589934592}
    )
    job_intervals: str = (
        ""  # "compute_matches:1440,expire_items:5": how often each scheduled job should succeed. Written by scripts/gcp.py
    )
    release: str = ""  # the git tag of the running image, set by the deploy script; tags every Sentry event
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
        for label, url in (("APP_URL", self.app_url), ("LANDING_URL", self.landing_url), ("API_URL", self.api_url)):
            if not re.fullmatch(r"https?://[^\s<>]+", url):
                # catches an unfilled <placeholder> or the word "auto" that the deploy script was meant to replace
                raise ValueError(f"{label} must be a full address starting with http:// or https:// (got '{url}')")
        parse_job_intervals(self.job_intervals)
        self.free_tier_limit_overrides()
        if self.backup_age_recipient and not re.fullmatch(r"age1[0-9a-z]{58}", self.backup_age_recipient):
            raise ValueError(
                "BACKUP_AGE_RECIPIENT must be an age PUBLIC key (age1...). Never put the private key (AGE-SECRET-KEY-...) here"
            )
        self._check_flags()
        self._check_beta_and_email()
        self._check_database()
        self._check_deployed_requirements()
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

    def _check_database(self) -> None:
        port = urlparse(self.database_url).port
        if port == 6543 and self.database_pooler != "transaction":
            # 6543 is the port of Supabase's transaction pooler. Without this setting Django would use server-side cursors, which
            # the pooler cannot keep alive between statements, and the first big list query would fail at random.
            raise ValueError("DATABASE_URL uses port 6543 (Supabase transaction pooler): set DATABASE_POOLER=transaction")

    def _check_deployed_requirements(self) -> None:
        """What staging and production need that a laptop does not. Checked last, so the more specific errors above come first."""
        if self.env not in ("staging", "production"):
            return
        if self.email_backend != "resend":
            raise ValueError("EMAIL_BACKEND must be resend in staging and production (console and disabled send nothing)")
        if self.embedding_provider != "fastembed":
            raise ValueError("EMBEDDING_PROVIDER must be fastembed in staging and production (fake vectors would ruin matching)")
        keys = {"gemini": self.gemini_api_key, "groq": self.groq_api_key, "anthropic": self.anthropic_api_key}
        if self.llm_provider != "none" and not keys.get(self.llm_provider):
            raise ValueError(
                f"LLM_PROVIDER={self.llm_provider} needs {self.llm_provider.upper()}_API_KEY in staging and production"
            )
        origins = self.csv(self.csrf_trusted_origins)
        if not origins:
            raise ValueError(
                "CSRF_TRUSTED_ORIGINS is required in staging and production: the Django admin login posts from the API origin"
            )
        if any(not re.fullmatch(r"https://[^/\s]+", o) for o in origins):
            raise ValueError("CSRF_TRUSTED_ORIGINS must be https:// origins without a path (a leading *. wildcard is allowed)")
        if self.redis_url and not self.redis_url.startswith("rediss://"):
            raise ValueError(
                "REDIS_URL must start with rediss:// (TLS) in staging and production; plain redis:// would cross the internet unencrypted"
            )

    def free_tier_limit_overrides(self) -> dict[str, int]:
        if not self.free_tier_limits.strip():
            return {}
        try:
            data = json.loads(self.free_tier_limits)
        except json.JSONDecodeError as exc:
            raise ValueError(f"FREE_TIER_LIMITS must be a JSON object: {exc}") from exc
        if not isinstance(data, dict) or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in data.values()):
            raise ValueError("FREE_TIER_LIMITS must be a JSON object of non-negative whole numbers")
        return data

    def csv(self, value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]


def load_config() -> Config:
    return Config()  # type: ignore[call-arg]
