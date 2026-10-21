import pytest
from django.apps import apps
from django.conf import settings

from seed.build import run

pytestmark = pytest.mark.django_db(transaction=True)


def counts():
    return {
        m._meta.label: m.objects.count()
        for m in apps.get_models()
        if m._meta.app_label in ("accounts", "startups", "jobs", "matching", "organisations")
    }


def test_reset_demo_is_idempotent_and_sized():
    first = run(settings.SEED_CITY)
    c1 = counts()
    run(settings.SEED_CITY)
    assert counts() == c1
    assert first["members"] == 300 and first["startups"] == 150
    assert 40 <= c1["matching.Capability"] <= 80 and 20 <= c1["matching.Trait"] <= 30
