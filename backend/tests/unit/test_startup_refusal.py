import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

BACKEND = Path(__file__).resolve().parents[2]
VALID = {
    "SUPABASE_URL": "https://x.supabase.co",
    "STORAGE_PROVIDER": "supabase",
    "SUPABASE_SERVICE_ROLE_KEY": "k",
    "DEBUG": "false",
    "SECRET_KEY": secrets.token_urlsafe(50),
    "CORS_PREVIEW_REGEX": "",
    "FEATURES": "pulse:everyone,daily_drop:everyone,circuits:testers",  # the dev .env turns payments on, which production refuses
    "RAZORPAY_KEY_ID": "",
}


def run_manage(*args, **env):
    full = {**os.environ, **VALID, **env}
    return subprocess.run(
        [sys.executable, "manage.py", *args], cwd=BACKEND, env=full, capture_output=True, text=True, timeout=120
    )


@pytest.mark.parametrize("env", ["staging", "production"])
def test_app_refuses_to_start_with_demo_auth_in_deployed_envs(env):
    r = run_manage("check", ENV=env, DEMO_AUTH="true")
    assert r.returncode != 0 and "DEMO_AUTH" in r.stderr


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_env_without_demo_auth_starts(env):
    r = run_manage("check", ENV=env, DEMO_AUTH="false")
    assert r.returncode == 0, r.stderr


def test_dev_and_demo_may_use_demo_auth():
    assert run_manage("check", ENV="dev", DEMO_AUTH="true", DEBUG="true").returncode == 0
    assert run_manage("check", ENV="demo", DEMO_AUTH="true").returncode == 0


@pytest.mark.parametrize("env", ["production", "staging", "demo"])
def test_django_deploy_checks_are_clean_for_every_public_env(env):
    """F-05: demo is public too, so it gets the same HTTPS/HSTS/secure-cookie settings."""
    r = run_manage("check", "--deploy", "--fail-level", "WARNING", ENV=env, DEMO_AUTH="true" if env == "demo" else "false")
    assert r.returncode == 0, r.stdout + r.stderr


def test_api_docs_and_openapi_are_not_served_in_production():
    code = (
        "import django; django.setup()\n"
        "from django.test.utils import setup_test_environment; setup_test_environment()\n"
        "from django.test import Client\n"
        "c = Client()\n"
        "print(*(c.get(u, secure=True).status_code for u in ('/api/openapi.json', '/api/docs', '/api/health')))\n"
    )
    env = {**os.environ, **VALID, "ENV": "production", "DEMO_AUTH": "false", "DJANGO_SETTINGS_MODULE": "circuit.settings"}
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)
    assert r.stdout.split()[-3:] == ["404", "404", "200"], r.stdout + r.stderr


def test_app_ready_guard_blocks_demo_auth_even_if_config_is_bypassed(settings):
    settings.DEMO_AUTH, settings.ENV = True, "staging"
    with pytest.raises(ImproperlyConfigured):
        apps.get_app_config("core").ready()
