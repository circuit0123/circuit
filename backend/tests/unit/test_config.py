import pytest
from pydantic import ValidationError

from circuit.config import Config

BASE = dict(
    env="dev",
    secret_key="aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5",
    database_url="postgres://u:p@h/d",
    redis_url="redis://h",
    allowed_hosts="h",
    cors_allowed_origins="http://h",
    app_url="http://a",
    landing_url="http://l",
    api_url="http://api",
    seed_city_name="C",
    seed_city_lat=1.0,
    seed_city_lng=2.0,
)


def make(**over):
    return Config(_env_file=None, **{**BASE, **over})


def test_dev_ok():
    assert make(demo_auth=True).env == "dev"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_demo_auth_refused_in_deployed_envs(env):
    with pytest.raises(ValidationError, match="DEMO_AUTH"):
        make(env=env, demo_auth=True, supabase_url="https://x.supabase.co")


def test_supabase_required_when_deployed():
    with pytest.raises(ValidationError, match="SUPABASE_URL"):
        make(env="staging")


def test_missing_required_variable_refuses_to_start():
    bad = {k: v for k, v in BASE.items() if k != "database_url"}
    with pytest.raises(ValidationError):
        Config(_env_file=None, **bad)


@pytest.mark.parametrize("env", ["staging", "production"])
def test_local_file_storage_refused_when_deployed(env):
    with pytest.raises(ValidationError, match="STORAGE_PROVIDER"):
        make(env=env, supabase_url="https://x.supabase.co")


def test_supabase_storage_needs_the_service_role_key_outside_dev():
    with pytest.raises(ValidationError, match="SERVICE_ROLE_KEY"):
        make(env="demo", supabase_url="https://x.supabase.co", storage_provider="supabase")
