"""The demo seed's social layer: build logs with drawn images, follows, requests and chats, and `reset_demo` stays idempotent."""

import pytest
from django.conf import settings
from django.db import connection

from apps.accounts.models import ConnectionRequest
from apps.matching import services as matching
from apps.messaging.models import Conversation
from apps.social.drop import build_all
from apps.social.models import Follow, MediaUpload, Post, PostMedia, Reply
from core.storage import get_storage
from seed.build import run
from tests.demo.conftest import person

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    run(settings.SEED_CITY)
    matching.compute_all()


def snapshot() -> dict:
    return {
        "posts": sorted(Post.objects.values_list("author_id", "body", "visibility")),
        "media": PostMedia.objects.count(),
        "replies": Reply.objects.count(),
        "follows": Follow.objects.count(),
        "requests": ConnectionRequest.objects.count(),
        "conversations": Conversation.objects.count(),
    }


def test_seed_has_build_logs_follows_requests_and_chats(seeded):
    s = snapshot()
    assert len(s["posts"]) >= 30 and s["media"] >= 15 and s["replies"] >= 3 and s["follows"] >= 10
    assert s["requests"] == 2 and s["conversations"] == 3


def test_every_seeded_image_is_stored_in_both_sizes_and_has_alt_text(seeded):
    files = get_storage().files
    for up in MediaUpload.objects.all():
        for name in ("w1440.webp", "w480.webp"):
            assert ("posts", f"{up.path}/{name}") in files
    assert not PostMedia.objects.filter(alt_text="").exists()


def test_seeded_minors_only_post_to_their_organisation(seeded):
    from apps.accounts.models import Member

    minors = Member.objects.filter(is_minor=True)
    assert minors.exists()
    assert not Post.objects.filter(author__in=minors).exclude(visibility="organisation").exists()


def test_reset_demo_twice_gives_the_same_social_data(seeded):
    first = snapshot()
    with connection.cursor() as cur:
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")  # TRUNCATE refuses while this test's own inserts have deferred checks
    run(settings.SEED_CITY)
    assert snapshot() == first


def test_ravi_sees_a_living_home_screen(seeded, client_for):
    ravi = person("ravi")
    c = client_for(ravi)
    pulse = c.get("/api/pulse").json()
    kinds = {i["kind"] for i in pulse["items"]}
    assert "post" in kinds and pulse["items"]
    assert c.get("/api/today").json()  # someone from his college or follows posted in the last day
    assert c.get("/api/me/follows").json()
    assert [r["note"][:12] for r in c.get("/api/connections/requests").json()] == ["Same departm"]
    assert len(c.get("/api/conversations?folder=requests").json()) == 1  # his own message to Divya, awaiting her answer


def test_the_daily_drop_job_fills_drops_after_the_seed(seeded, client_for):
    assert build_all()["built"] > 150
    cards = client_for(person("ravi")).get("/api/drop/today").json()["cards"]
    assert 1 <= len(cards) <= 3
    assert all(c["strength"] in ("strong", "good") for c in cards)  # nothing weaker is ever dropped
    assert any(c["help_with"] for c in cards)  # most cards can say what they offer that he needs
