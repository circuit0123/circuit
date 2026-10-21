import pytest
from django.test import Client

from seed.personas import PERSONAS, auth_uuid

pytestmark = pytest.mark.django_db


@pytest.fixture
def personas(make_member):
    for key, (role, name) in PERSONAS.items():
        make_member(role, auth_user_id=auth_uuid(key), display_name=name)


def post_token(persona):
    return Client().post("/api/demo/token", {"persona": persona}, content_type="application/json")


def test_endpoints_404_when_demo_auth_off(personas):
    assert Client().get("/api/demo/personas").status_code == 404
    assert post_token("asha").status_code == 404


def test_dev_lists_personas_and_issues_a_working_token(personas, settings):
    settings.DEMO_AUTH, settings.ENV = True, "dev"
    listed = Client().get("/api/demo/personas").json()
    assert {p["key"] for p in listed} == set(PERSONAS)
    r = post_token("meenakshi")
    assert r.status_code == 200
    me = Client().get("/api/me", HTTP_AUTHORIZATION=f"Bearer {r.json()['access_token']}")
    assert me.status_code == 200 and me.json()["role"] == "partner_admin"


def test_unknown_persona_404(personas, settings):
    settings.DEMO_AUTH, settings.ENV = True, "dev"
    assert post_token("nobody").status_code == 404


def test_demo_env_needs_demo_public(personas, settings):
    settings.DEMO_AUTH, settings.ENV, settings.DEMO_PUBLIC = True, "demo", False
    assert Client().get("/api/demo/personas").status_code == 404
    settings.DEMO_PUBLIC = True
    assert Client().get("/api/demo/personas").status_code == 200


def test_public_demo_never_issues_super_admin(personas, settings):
    settings.DEMO_AUTH, settings.ENV, settings.DEMO_PUBLIC = True, "demo", True
    assert "admin" not in {p["key"] for p in Client().get("/api/demo/personas").json()}
    assert post_token("admin").status_code == 404


def test_dev_may_use_admin_persona(personas, settings):
    settings.DEMO_AUTH, settings.ENV = True, "dev"
    assert post_token("admin").status_code == 200


def test_unseeded_database_gives_a_helpful_404(settings):
    settings.DEMO_AUTH, settings.ENV = True, "dev"
    r = post_token("asha")
    assert r.status_code == 404 and "reset-demo" in r.json()["error"]["message"]
