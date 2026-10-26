"""B7 part 1: GET /api/search: one call for people, startups and roles."""

import pytest

from apps.jobs.models import Job, JobCapability
from apps.matching.models import Capability

pytestmark = pytest.mark.django_db


def search(client, q):
    r = client.get("/api/search", {"q": q})
    assert r.status_code == 200, r.content
    return r.json()


@pytest.fixture
def town(lists, make_member, make_startup):
    founder = make_member("founder", display_name="Ananya Rao")
    verified = make_startup(name="Anand Labs", domain="anand.io", sector="healthtech", hiring=True, claimed_by=founder)
    other = make_startup(name="Zenith Works", domain="zenith.io", sector="fintech", hiring=True)
    job = Job.objects.create(startup=verified, title="Analytics intern", is_open=True)
    JobCapability.objects.create(job=job, capability=Capability.objects.get(slug="seo"), required=True)
    Job.objects.create(startup=other, title="Backend intern", is_open=True)
    return founder, verified, other, job


def test_one_call_returns_the_three_lists(town, make_member, client_for):
    me = make_member("student", display_name="Ravi")
    body = search(client_for(me), "an")
    assert [p["display_name"] for p in body["people"]] == ["Ananya Rao"]
    assert [s["name"] for s in body["startups"]] == ["Anand Labs"]
    assert [j["title"] for j in body["jobs"]] == ["Analytics intern"]


def test_people_are_found_by_name_only(town, make_member, client_for):
    make_member("mentor", display_name="Meera", bio="I love analytics and an")
    assert search(client_for(make_member("student")), "analytics")["people"] == []


def test_startups_by_sector_and_jobs_by_skill_or_startup(town, make_member, client_for):
    c = client_for(make_member("student"))
    assert [s["name"] for s in search(c, "fintech")["startups"]] == ["Zenith Works"]
    assert [j["title"] for j in search(c, "zenith")["jobs"]] == ["Backend intern"]
    assert [j["title"] for j in search(c, Capability.objects.get(slug="seo").name)["jobs"]] == ["Analytics intern"]


def test_hidden_minor_blocked_deleted_and_admin_people_never_appear(town, make_member, block, client_for):
    me = make_member("student")
    hidden = make_member("mentor", display_name="Zed Hidden", profile_visibility="hidden")
    kid = make_member("student", display_name="Zed Kid", is_minor=True)
    blocked = make_member("mentor", display_name="Zed Blocked")
    gone = make_member("mentor", display_name="Zed Gone")
    gone.deleted_at = gone.created_at
    gone.save()
    admin = make_member("super_admin", display_name="Zed Admin")
    sim = make_member("mentor", display_name="Zed Sim", is_simulated=True)
    ok = make_member("mentor", display_name="Zed Fine")
    block(me, blocked)
    assert [p["display_name"] for p in search(client_for(me), "zed")["people"]] == ["Zed Fine"]


def test_you_do_not_find_yourself(town, make_member, client_for):
    me = make_member("student", display_name="Ravi Unique")
    assert search(client_for(me), "unique")["people"] == []


def test_an_under_18_finds_only_connections_and_verified_roles(town, make_member, connect, client_for):
    kid = make_member("student", display_name="Kid", is_minor=True)
    friend = make_member("mentor", display_name="Anil Friend")
    make_member("mentor", display_name="Anil Stranger")
    connect(kid, friend)
    c = client_for(kid)
    assert [p["display_name"] for p in search(c, "anil")["people"]] == ["Anil Friend"]
    assert search(c, "backend")["jobs"] == []  # Zenith Works is not verified
    assert [j["title"] for j in search(c, "analytics")["jobs"]] == ["Analytics intern"]
    pins = {s["name"]: s for s in search(c, "works")["startups"]}
    assert pins["Zenith Works"]["hiring"] is False and pins["Zenith Works"]["open_roles"] == 0


def test_each_list_is_capped_at_ten(lists, make_member, client_for):
    for i in range(14):
        make_member("mentor", display_name=f"Priya {i}")
    assert len(search(client_for(make_member("student")), "priya")["people"]) == 10


def test_a_single_character_is_a_422_and_so_is_nothing(make_member, client_for):
    c = client_for(make_member("student"))
    assert c.get("/api/search", {"q": "a"}).status_code == 422
    assert c.get("/api/search").status_code == 422


def test_a_blank_search_returns_empty_lists_without_using_the_limit(make_member, client_for):
    assert search(client_for(make_member("student")), "   ") == {"people": [], "startups": [], "jobs": []}


def test_search_is_rate_limited_and_needs_sign_in(town, make_member, client_for, client, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "search": (2, 3600)}
    c = client_for(make_member("student"))
    assert [c.get("/api/search", {"q": "an"}).status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/api/search", {"q": "an"}).status_code == 401


def test_search_results_carry_no_private_fields(town, make_member, client_for):
    body = client_for(make_member("student")).get("/api/search", {"q": "an"}).content.decode()
    for word in ("email", "view_count", "interest_count", "score"):
        assert word not in body
