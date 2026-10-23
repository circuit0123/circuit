"""The demo stories run against the real seed (`reset_demo` data), with matches computed, like the demo environment."""

import pytest
from django.conf import settings

from apps.accounts.models import Member
from apps.matching import services as matching
from seed.build import run
from seed.personas import auth_uuid


@pytest.fixture
def seeded():
    run(settings.SEED_CITY)
    matching.compute_all()


def person(key: str) -> Member:
    return Member.objects.get(auth_user_id=auth_uuid(key))
