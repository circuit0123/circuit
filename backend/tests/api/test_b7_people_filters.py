"""B7 part 1: filters and card fields on GET /api/matches (Discover → People)."""

import pytest
from django.contrib.gis.geos import Point

from apps.matching import services
from apps.matching.models import Capability, Need, Offer

pytestmark = pytest.mark.django_db
CHENNAI = Point(80.2707, 13.0827, srid=4326)


def offer(m, slug):
    return Offer.objects.create(member=m, capability=Capability.objects.get(slug=slug))


@pytest.fixture
def world(lists, make_member, settings):
    """A seeker in Chennai and four givers of SEO with different roles, levels and places."""
    seeker = make_member("founder", display_name="Seeker")
    seeker.location = CHENNAI
    seeker.save()
    Need.objects.create(member=seeker, capability=Capability.objects.get(slug="seo"))
    givers = {}
    for key, role, level, dx in [("near_mentor", "mentor", 3, 0.02), ("near_student", "student", 1, 0.03),
                                 ("far_mentor", "mentor", 2, 1.5), ("no_place", "mentor", 1, None)]:  # fmt: skip
        m = make_member(role, display_name=key, level=level, bio=f"Hi, I am {key}. " + "x" * 200)
        if dx is not None:
            m.location = Point(80.2707 + dx, 13.0827, srid=4326)
            m.save()
        offer(m, "seo")
        givers[key] = m
    services.compute_all()
    return seeker, givers


def names(client, query=""):
    r = client.get("/api/matches" + query)
    assert r.status_code == 200, r.content
    return sorted(m["display_name"] for m in r.json()["items"])


def test_no_filter_returns_everyone_with_the_new_card_fields(world, client_for):
    seeker, givers = world
    items = client_for(seeker).get("/api/matches").json()["items"]
    assert len(items) == 4
    one = next(i for i in items if i["display_name"] == "near_mentor")
    assert one["headline"].startswith("Hi, I am near_mentor") and len(one["headline"]) == 140
    assert one["capabilities"] == [Capability.objects.get(slug="seo").name] and one["photo"] is None


def test_filter_by_role(world, client_for):
    seeker, _ = world
    assert names(client_for(seeker), "?role=student") == ["near_student"]
    assert names(client_for(seeker), "?role=mentor") == ["far_mentor", "near_mentor", "no_place"]
    assert client_for(seeker).get("/api/matches?role=admin").status_code == 422


def test_filter_verified_means_level_two_or_three(world, client_for):
    seeker, _ = world
    assert names(client_for(seeker), "?verified=true") == ["far_mentor", "near_mentor"]


def test_filter_by_capability(world, client_for):
    seeker, givers = world
    offer(givers["near_student"], "ui-design")
    assert names(client_for(seeker), "?capability=ui-design") == ["near_student"]
    assert names(client_for(seeker), "?capability=nope") == []
    assert len(names(client_for(seeker), "?capability=seo")) == 4


@pytest.mark.parametrize("km,expected", [(5, ["near_mentor", "near_student"]), (50, ["near_mentor", "near_student"]),
                                         (500, None)])  # fmt: skip
def test_filter_by_distance_uses_the_coarse_choices_only(world, client_for, km, expected):
    seeker, _ = world
    if expected is None:
        assert client_for(seeker).get(f"/api/matches?within_km={km}").status_code == 422
    else:
        assert names(client_for(seeker), f"?within_km={km}") == expected  # far_mentor is ~160 km away; no_place has none


def test_no_distance_or_location_is_ever_returned(world, client_for):
    seeker, _ = world
    body = client_for(seeker).get("/api/matches?within_km=25").content.decode()
    for word in ("distance", "lat", "lng", "location"):
        assert word not in body


def test_filters_combine(world, client_for):
    seeker, _ = world
    assert names(client_for(seeker), "?role=mentor&verified=true&within_km=25") == ["near_mentor"]


def test_filters_and_bridge_apply_before_paging(world, client_for):
    seeker, _ = world
    r = client_for(seeker).get("/api/matches?role=mentor&limit=1").json()
    assert r["count"] == 3 and len(r["items"]) == 1 and r["next_offset"] == 1


def test_hidden_and_blocked_people_stay_out_under_any_filter(world, block, client_for):
    seeker, givers = world
    givers["near_mentor"].profile_visibility = "hidden"
    givers["near_mentor"].save()
    block(seeker, givers["far_mentor"])
    assert names(client_for(seeker), "?role=mentor") == ["no_place"]
