"""The app refuses to start when it is set up wrongly (circuit/config.py). One test per rule: the refusal AND the valid case, so a rule
cannot pass by refusing everything."""

import json
import re

import pytest
from pydantic import ValidationError

from circuit.config import Config
from tests.unit.test_config import BASE, DEPLOYED, make
from tests.unit.test_startup_refusal import run_manage

PROD = dict(DEPLOYED, env="production", allowed_hosts="api.example.com", cors_allowed_origins="https://app.example.com")


def prod(**over):
    return make(**{**PROD, **over})


# ---- the four rules from the deploy brief -------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ["staging", "production"])
def test_demo_auth_refuses_to_start_in_staging_and_production(env):
    with pytest.raises(ValidationError, match="DEMO_AUTH"):
        make(**{**PROD, "env": env}, demo_auth=True)
    assert make(**{**PROD, "env": env}, demo_auth=False)


@pytest.mark.parametrize("env", ["dev", "demo", "staging"])
def test_live_razorpay_keys_refuse_to_start_outside_production(env):
    extra = {} if env == "dev" else {**PROD, "env": env}
    with pytest.raises(ValidationError, match="live keys"):
        make(**extra, razorpay_key_id="rzp_live_abc")
    assert make(**extra, razorpay_key_id="rzp_test_abc")


def test_live_razorpay_keys_are_fine_in_production():
    assert prod(razorpay_key_id="rzp_live_abc", features="pulse:everyone,promotions:everyone,payments:everyone")


@pytest.mark.parametrize(
    "features, dependency",
    [
        ("promotions:everyone", "pulse"),
        ("pulse:everyone,payments:everyone", "promotions"),
        ("pulse:testers,payments:testers", "promotions"),
    ],
)
def test_a_flag_without_its_dependency_refuses_to_start(features, dependency):
    with pytest.raises(ValidationError, match=f"needs '{dependency}'"):
        prod(features=features)
    assert prod(features="pulse:everyone,promotions:everyone")


REQUIRED = [
    "env", "secret_key", "database_url", "redis_url", "allowed_hosts", "cors_allowed_origins",
    "app_url", "landing_url", "api_url", "seed_city_name", "seed_city_lat", "seed_city_lng",
]  # fmt: skip


@pytest.mark.parametrize("field", REQUIRED)
def test_a_missing_required_variable_refuses_to_start_and_names_it(field):
    values = {k: v for k, v in BASE.items() if k != field}
    with pytest.raises(ValidationError) as err:
        Config(_env_file=None, **values)
    assert field in str(err.value).lower()


def test_a_missing_variable_stops_the_real_process_too():
    result = run_manage("check", ENV="production", DEMO_AUTH="false", DATABASE_URL="")
    assert result.returncode != 0 and "DATABASE_URL" in result.stderr.upper()


@pytest.mark.parametrize("field", ["app_url", "landing_url", "api_url"])
@pytest.mark.parametrize("value", ["auto", "<https://app.yourdomain>", "app.example.com", "ftp://x.example"])
def test_urls_must_be_real_addresses_so_an_unfilled_placeholder_cannot_start(field, value):
    with pytest.raises(ValidationError, match=field.upper()):
        make(**{field: value})


# ---- rules for staging and production only ------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize("backend", ["console", "disabled"])
def test_deployed_envs_must_really_send_email(env, backend):
    with pytest.raises(ValidationError, match="EMAIL_BACKEND"):
        make(**{**PROD, "env": env, "email_backend": backend})


def test_deployed_envs_must_use_real_embeddings():
    with pytest.raises(ValidationError, match="EMBEDDING_PROVIDER"):
        prod(embedding_provider="fake")


@pytest.mark.parametrize(
    "provider, key", [("gemini", "gemini_api_key"), ("groq", "groq_api_key"), ("anthropic", "anthropic_api_key")]
)
def test_the_llm_provider_in_use_needs_its_key(provider, key):
    clean = {**PROD, "groq_api_key": ""}
    with pytest.raises(ValidationError, match=f"{provider.upper()}_API_KEY"):
        make(**{**clean, "llm_provider": provider})
    assert make(**{**clean, "llm_provider": provider, key: "k"})


def test_a_key_for_a_different_provider_does_not_count():
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        prod(llm_provider="anthropic", groq_api_key="only-the-wrong-one")


@pytest.mark.parametrize("value", ["", "http://api.example.com", "https://api.example.com/admin", "api.example.com"])
def test_csrf_trusted_origins_must_be_https_origins(value):
    with pytest.raises(ValidationError, match="CSRF_TRUSTED_ORIGINS"):
        prod(csrf_trusted_origins=value)


def test_csrf_trusted_origins_accept_a_wildcard_subdomain_and_several_origins():
    assert prod(csrf_trusted_origins="https://*.run.app,https://api.example.com")


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_redis_must_use_tls(env):
    with pytest.raises(ValidationError, match="rediss://"):
        make(**{**PROD, "env": env, "redis_url": "redis://default:p@x.upstash.io:6379"})
    assert make(**{**PROD, "env": env, "redis_url": "rediss://default:p@x.upstash.io:6379"})


@pytest.mark.parametrize("field", ["email_backend", "embedding_provider", "csrf_trusted_origins", "redis_url"])
def test_laptops_and_demo_are_not_held_to_the_deployed_rules(field):
    # dev uses console email, fake vectors and a local Redis; demo disables email
    assert make(env="dev")
    assert make(env="demo", supabase_url="https://x.supabase.co", storage_provider="supabase", supabase_service_role_key="k")


# ---- database pooler -------------------------------------------------------------------------------------------------------


def test_port_6543_without_the_pooler_setting_refuses_to_start():
    with pytest.raises(ValidationError, match="DATABASE_POOLER=transaction"):
        make(database_url="postgres://u:p@aws-0.pooler.supabase.com:6543/postgres")
    assert make(database_url="postgres://u:p@aws-0.pooler.supabase.com:6543/postgres", database_pooler="transaction")
    assert make(database_url="postgres://u:p@db.supabase.co:5432/postgres")  # direct connection: nothing to set


def test_unknown_pooler_mode_is_refused():
    with pytest.raises(ValidationError, match="database_pooler"):
        make(database_pooler="pgbouncer")


def _db_settings(**env):
    code = (
        "import json; from django.conf import settings; from django.db import connection; d = settings.DATABASES['default'];"
        "print(json.dumps({'cursors': d.get('DISABLE_SERVER_SIDE_CURSORS'), 'age': d['CONN_MAX_AGE'], 'health': d['CONN_HEALTH_CHECKS'],"
        "'options': d['OPTIONS'], 'prepare': connection.get_connection_params()['prepare_threshold']}))"
    )
    result = run_manage("shell", "-c", code, DEMO_AUTH="false", **env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_transaction_pooler_switches_off_server_side_cursors_and_never_prepares_statements():
    db = _db_settings(
        DATABASE_URL="postgres://u:p@aws-0.pooler.supabase.com:6543/postgres", DATABASE_POOLER="transaction", ENV="production"
    )
    assert db["cursors"] is True  # .iterator() fetches in pages instead of holding a cursor on one server connection
    assert (
        db["prepare"] is None
    )  # prepared statements live on one server connection; the pooler hands out another each transaction
    assert db["age"] == 60 and db["health"] is True


def test_direct_connection_keeps_server_side_cursors():
    assert not _db_settings(DATABASE_POOLER="direct", ENV="dev")["cursors"]


def test_deployed_database_connections_require_tls_except_to_localhost():
    remote = _db_settings(
        DATABASE_URL="postgres://u:p@aws-0.pooler.supabase.com:6543/postgres", DATABASE_POOLER="transaction", ENV="production"
    )
    assert remote["options"] == {"sslmode": "require"}
    assert _db_settings(DATABASE_URL="postgres://u:p@localhost:5432/circuit", ENV="production")["options"] == {}
    assert _db_settings(DATABASE_URL="postgres://u:p@db.example.com:5432/x", ENV="dev")["options"] == {}


# ---- the committed deploy files and .env.example agree with the code ---------------------------------------------------------


def test_every_config_variable_is_documented_in_env_example():
    from django.conf import settings

    text = (settings.BASE_DIR.parent / ".env.example").read_text()
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE))
    missing = [name.upper() for name in Config.model_fields if name.upper() not in documented]
    assert not missing, f"add these to .env.example: {missing}"
