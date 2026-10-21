"""Environment configuration, validated once at startup.

A missing or inconsistent variable raises here, so the app refuses to start
instead of failing later in a request.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent.parent


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

    @model_validator(mode="after")
    def _check_env_rules(self) -> "Config":
        deployed = self.env in ("staging", "production")
        if deployed and self.demo_auth:
            raise ValueError("DEMO_AUTH must be false when ENV is staging or production")
        if self.demo_auth and self.env not in ("dev", "demo"):
            raise ValueError("DEMO_AUTH is only allowed in dev and demo")
        if deployed and self.debug:
            raise ValueError("DEBUG must be false in staging and production")
        if deployed and not self.supabase_url:
            raise ValueError("SUPABASE_URL is required in staging and production")
        if deployed and self.llm_provider == "fake":
            raise ValueError("LLM_PROVIDER=fake is only for tests")
        if self.env == "production" and self.cors_preview_regex:
            raise ValueError("CORS_PREVIEW_REGEX must be empty in production")
        return self

    def csv(self, value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]


def load_config() -> Config:
    return Config()  # type: ignore[call-arg]
