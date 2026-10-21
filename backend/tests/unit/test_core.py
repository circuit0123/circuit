import json

import pytest
import redis
from django.db import DatabaseError, connection
from pydantic import BaseModel

from core import cache, embeddings, llm
from core.graph import find_cycles, neighbours
from core.pagination import PageParams, paginate

pytestmark = pytest.mark.django_db


def test_pagination_shape():
    page = paginate(list(range(25)), PageParams(limit=10, offset=20))
    assert page == {"items": [20, 21, 22, 23, 24], "count": 25, "next_offset": None}
    assert paginate(list(range(25)), PageParams(limit=10, offset=0))["next_offset"] == 10


def test_cache_roundtrip_and_window():
    c = cache.get_cache()
    c.set_json("k", {"a": 1})
    assert c.get_json("k") == {"a": 1}
    assert [c.incr_window("w", 60) for _ in range(3)] == [1, 2, 3]


def test_cache_degrades_when_redis_down(caplog):
    class Broken:
        def get(self, *a):
            raise redis.ConnectionError("down")

        def ping(self):
            raise redis.ConnectionError("down")

    c = cache.Cache(Broken())
    assert c.get_json("k") is None
    assert c.ping() is False


def test_fake_embeddings_are_deterministic_and_related():
    e = embeddings.FakeEmbeddingProvider()
    a, a2, b = e.embed(["marketing for biotech", "marketing for biotech", "quantum lab"])
    assert a == a2 and len(a) == 384
    assert embeddings.cosine(a, a) > embeddings.cosine(a, b)


class Out(BaseModel):
    slugs: list[str]


def test_llm_valid_invalid_and_error(fake_llm):
    fake_llm.response = json.dumps({"slugs": ["seo"]})
    assert llm.extract_json("s", "u", Out) == Out(slugs=["seo"])
    fake_llm.response = "not json"
    assert llm.extract_json("s", "u", Out) is None
    fake_llm.response = json.dumps({"wrong": 1})
    assert llm.extract_json("s", "u", Out) is None


def test_llm_failure_retries_then_falls_back(fake_llm, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    fake_llm.error = TimeoutError("slow")
    assert llm.extract_json("s", "u", Out) is None
    assert fake_llm.calls == llm.MAX_ATTEMPTS


def test_find_cycles_on_known_graph():
    assert find_cycles([(1, 2), (2, 3), (3, 1), (3, 4), (4, 5)]) == [[1, 2, 3]]
    assert find_cycles([(1, 2), (2, 1)]) == []  # a 2-cycle is not a 3-person loop


def test_neighbours_recursive_sql():
    import uuid

    from apps.accounts.models import Connection, Member

    ms = [Member.objects.create(auth_user_id=uuid.uuid4()) for _ in range(4)]
    a, b, c, d = sorted(ms, key=lambda m: m.pk)
    Connection.objects.create(member_a=a, member_b=b, strength=0.9)
    Connection.objects.create(member_a=b, member_b=c, strength=0.6)
    Connection.objects.create(member_a=c, member_b=d, strength=0.8)
    n = neighbours(a.pk, max_hops=2)
    assert set(n) == {b.pk, c.pk}
    assert n[c.pk]["hops"] == 2 and n[c.pk]["path"] == [a.pk, b.pk, c.pk] and n[c.pk]["strength"] == 0.6


def test_every_table_has_rls_enabled():
    with connection.cursor() as cur:
        cur.execute(
            "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE nspname='public' AND relkind='r' AND NOT relrowsecurity AND relname <> 'spatial_ref_sys'"
        )
        assert cur.fetchall() == []


def test_events_are_append_only():
    from django.db import transaction

    from apps.events.models import Event

    e = Event.objects.create(type="x")
    with pytest.raises(DatabaseError), transaction.atomic():
        Event.objects.filter(pk=e.pk).update(type="y")
    with pytest.raises(DatabaseError), transaction.atomic():
        e.delete()


def test_minor_profiles_hidden_by_default():
    import uuid

    from apps.accounts.models import Member

    m = Member.objects.create(auth_user_id=uuid.uuid4(), is_minor=True)
    assert m.profile_visibility == "hidden"
