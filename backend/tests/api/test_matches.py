import pytest
from django.contrib.gis.geos import Point

from apps.accounts.models import Connection
from apps.events.models import Event
from apps.matching import services
from apps.matching.models import Capability, MatchResult, MemberTrait, Need, Offer, Trait
from apps.moderation.models import Block
from apps.startups.models import StartupMember
from core.cache import get_cache

pytestmark = pytest.mark.django_db
CHENNAI, BENGALURU = Point(80.27, 13.08, srid=4326), Point(77.59, 12.97, srid=4326)


def need(m, slug, text=""):
    return Need.objects.create(member=m, capability=Capability.objects.get(slug=slug), description=text)


def offer(m, slug, text=""):
    return Offer.objects.create(member=m, capability=Capability.objects.get(slug=slug), description=text)


def trait(m, slug):
    return MemberTrait.objects.create(member=m, trait=Trait.objects.get(slug=slug))


def in_sector(member, startup):
    StartupMember.objects.create(startup=startup, member=member, role="founder")


def matched(member):
    return set(MatchResult.objects.filter(member=member).values_list("candidate_id", flat=True))


@pytest.fixture
def pair(lists, make_member):
    """Seeker needs SEO; giver offers it."""
    seeker, giver = make_member("founder"), make_member("mentor")
    need(seeker, "seo")
    offer(giver, "seo")
    return seeker, giver


# -- compute_matches ---------------------------------------------------------------------------------
def test_a_need_meets_an_offer_with_a_reason(pair, client_for):
    seeker, giver = pair
    stats = services.compute_all()
    assert matched(seeker) == {giver.pk} and matched(giver) == {seeker.pk}  # a fit is shown to both sides
    assert stats["members"] == 2 and stats["matches"] == 2
    assert MatchResult.objects.get(member=giver).reason.startswith("You offer")
    row = client_for(seeker).get("/api/matches").json()["items"][0]
    assert (
        row["candidate_id"] == giver.pk and row["reason"].startswith("They offer") and row["strength"] in ("strong", "good", None)
    )
    assert Event.objects.filter(type="matches.computed").count() == 1


def test_two_way_help_scores_higher_than_one_way(lists, make_member):
    a, b, c = make_member("founder"), make_member("founder"), make_member("mentor")
    need(a, "seo")
    offer(b, "seo")
    need(b, "recruiting")
    offer(a, "recruiting")  # a and b help each other
    offer(c, "seo")  # c only helps a
    services.compute_all()
    scores = dict(MatchResult.objects.filter(member=a).values_list("candidate_id", "score"))
    assert scores[b.pk] > scores[c.pk]
    assert MatchResult.objects.get(member=a, candidate=b).reason.startswith("You can help each other")


def test_computing_twice_gives_the_same_rows_and_follows_changes(pair):
    seeker, giver = pair
    services.compute_all()
    first = list(MatchResult.objects.values_list("member_id", "candidate_id", "score"))
    services.compute_all()
    assert list(MatchResult.objects.values_list("member_id", "candidate_id", "score")) == first
    Need.objects.filter(member=seeker).delete()
    services.compute_all()
    assert MatchResult.objects.count() == 0


def test_similar_text_on_different_capabilities_is_a_partial_match(lists, make_member):
    a, b = make_member("founder"), make_member("mentor")
    need(a, "seo", "grow organic search traffic for our b2b site")
    offer(b, "content-marketing", "grow organic search traffic for our b2b site")  # same words, different capability
    services.compute_all()
    m = MatchResult.objects.get(member=a, candidate=b)
    assert m.components["complementarity"] == pytest.approx(0.6 * 0.8)


def test_unrelated_people_are_not_matched(lists, make_member):
    a, b = make_member("founder"), make_member("mentor")
    need(a, "seo", "organic search")
    offer(b, "fundraising", "raising a seed round")
    services.compute_all()
    assert MatchResult.objects.count() == 0


# -- who can be recommended --------------------------------------------------------------------------
def test_hidden_blocked_suspended_full_and_admin_candidates_are_left_out(lists, make_member):
    from django.utils import timezone

    seeker = make_member("founder")
    need(seeker, "seo")
    ok = make_member("mentor")
    hidden = make_member("mentor", profile_visibility="hidden")
    blocked = make_member("mentor")
    suspended = make_member("mentor", suspended_at=timezone.now())
    full = make_member("mentor", open_intro_slots=0)
    admin = make_member("partner_admin")
    for m in (ok, hidden, blocked, suspended, full, admin):
        offer(m, "seo")
    Block.objects.create(blocker=seeker, blocked=blocked)
    services.compute_all()
    assert matched(seeker) == {ok.pk}
    assert matched(admin) == set()


def test_a_block_either_way_hides_the_match(lists, make_member):
    a, b = make_member("founder"), make_member("mentor")
    need(a, "seo")
    offer(b, "seo")
    need(b, "seo")
    offer(a, "seo")
    Block.objects.create(blocker=b, blocked=a)
    services.compute_all()
    assert matched(a) == matched(b) == set()


def test_students_are_matched_only_within_walking_distance_of_the_city(lists, make_member):
    student = make_member("student", location=CHENNAI, city="Chennai")
    near = make_member("founder", location=Point(80.28, 13.09, srid=4326), city="Chennai")
    far = make_member("founder", location=BENGALURU, city="Bengaluru")
    nowhere = make_member("founder", city="Pune")
    need(student, "mentoring")
    for f in (near, far, nowhere):
        offer(f, "mentoring")
    services.compute_all()
    assert matched(student) == {near.pk}


def test_distance_filter_applies_from_the_founders_side_too(lists, make_member):
    founder = make_member("founder", location=BENGALURU, city="Bengaluru")
    student = make_member("student", location=CHENNAI, city="Chennai")
    need(founder, "frontend-dev")
    offer(student, "frontend-dev")
    services.compute_all()
    assert matched(founder) == set()


def test_students_without_a_location_fall_back_to_the_same_city(lists, make_member):
    student = make_member("student", city="Chennai")
    same, other = make_member("mentor", city="chennai"), make_member("mentor", city="Pune")
    need(student, "mentoring")
    offer(same, "mentoring")
    offer(other, "mentoring")
    services.compute_all()
    assert matched(student) == {same.pk}


def test_minors_only_match_people_they_already_know(lists, make_member, make_org):
    org = make_org()
    minor = make_member("student", org=org, is_minor=True, city="Chennai")
    teammate = make_member("mentor", org=org, city="Chennai")
    stranger = make_member("mentor", city="Chennai")
    friend = make_member("mentor", city="Chennai")
    Connection.objects.create(member_a_id=min(minor.pk, friend.pk), member_b_id=max(minor.pk, friend.pk))
    need(minor, "mentoring")
    for m in (teammate, stranger, friend):
        offer(m, "mentoring")
    services.compute_all()
    assert matched(minor) == {teammate.pk, friend.pk}
    adult = make_member("founder", city="Chennai")
    need(adult, "mentoring")
    offer(minor, "mentoring")  # under-18 profiles are hidden by default, so strangers never see them
    services.compute_all()
    assert minor.pk not in matched(adult)


def test_one_person_is_shown_in_a_limited_number_of_lists(lists, make_member, settings):
    settings.MATCH_MAX_APPEARANCES = 2
    giver = make_member("mentor")
    offer(giver, "seo")
    seekers = [make_member("founder") for _ in range(4)]
    for s in seekers:
        need(s, "seo")
    services.compute_all()
    assert MatchResult.objects.filter(candidate=giver).count() == 2


def test_a_list_never_exceeds_the_top_n(lists, make_member, settings):
    settings.MATCH_TOP_N = 3
    seeker = make_member("founder")
    need(seeker, "seo")
    for _ in range(6):
        offer(make_member("mentor"), "seo")
    services.compute_all()
    assert MatchResult.objects.filter(member=seeker).count() == 3


# -- bridge and trust --------------------------------------------------------------------------------
def test_matches_across_sectors_are_bridge_matches(lists, make_member, make_startup, client_for):
    seeker, same, other = make_member("founder"), make_member("founder"), make_member("founder")
    in_sector(seeker, make_startup("Bio", "bio.io", sector="biotech"))
    in_sector(same, make_startup("Bio2", "bio2.io", sector="biotech"))
    in_sector(other, make_startup("Deep", "deep.io", sector="deeptech"))
    need(seeker, "b2b-marketing")
    offer(same, "b2b-marketing")
    offer(other, "b2b-marketing")
    services.compute_all()
    c = client_for(seeker)
    items = {r["candidate_id"]: r for r in c.get("/api/matches").json()["items"]}
    assert items[other.pk]["is_bridge"] is True and items[same.pk]["is_bridge"] is False
    assert items[other.pk]["sector"] == "deeptech"
    assert [r["candidate_id"] for r in c.get("/api/matches?bridge=true").json()["items"]] == [other.pk]
    assert [r["candidate_id"] for r in c.get("/api/matches?bridge=false").json()["items"]] == [same.pk]


def test_shared_traits_and_connections_raise_the_score_and_show_in_the_reason(lists, make_member):
    seeker, plain, close = make_member("founder"), make_member("mentor"), make_member("mentor")
    need(seeker, "seo")
    offer(plain, "seo")
    offer(close, "seo")
    for m in (seeker, close):
        trait(m, "long-sales-cycle")
    Connection.objects.create(member_a_id=min(seeker.pk, close.pk), member_b_id=max(seeker.pk, close.pk), strength=0.9)
    services.compute_all()
    scores = dict(MatchResult.objects.filter(member=seeker).values_list("candidate_id", "score"))
    assert scores[close.pk] > scores[plain.pk]
    reason = MatchResult.objects.get(member=seeker, candidate=close).reason
    assert "long sales cycle" in reason and "already connected" in reason


def test_reasons_never_contain_names(pair):
    seeker, giver = pair
    services.compute_all()
    for m in MatchResult.objects.all():
        assert seeker.display_name not in m.reason and giver.display_name not in m.reason


# -- reading -----------------------------------------------------------------------------------------
def test_reads_come_from_redis_then_postgres_and_recheck_visibility(pair, client_for):
    seeker, giver = pair
    services.compute_all()
    c = client_for(seeker)
    assert get_cache().get_json(f"matches:{seeker.pk}")
    assert len(c.get("/api/matches").json()["items"]) == 1
    get_cache().delete(f"matches:{seeker.pk}")  # Redis cold or down: Postgres answers and refills the cache
    assert len(c.get("/api/matches").json()["items"]) == 1
    assert get_cache().get_json(f"matches:{seeker.pk}")
    Block.objects.create(blocker=seeker, blocked=giver)  # blocked after the last run: gone at once
    assert c.get("/api/matches").json() == {"items": [], "count": 0, "next_offset": None}


def test_suspended_or_hidden_matches_disappear_before_the_next_run(pair, client_for):
    from django.utils import timezone

    seeker, giver = pair
    services.compute_all()
    giver.suspended_at = timezone.now()
    giver.save()
    assert client_for(seeker).get("/api/matches").json()["items"] == []
    services.compute_all()
    assert MatchResult.objects.count() == 0


def test_my_matches_are_mine_only_and_paginated(lists, make_member, client_for):
    seeker, other = make_member("founder"), make_member("founder")
    need(seeker, "seo")
    for _ in range(3):
        offer(make_member("mentor"), "seo")
    services.compute_all()
    page = client_for(seeker).get("/api/matches?limit=2").json()
    assert page["count"] == 3 and len(page["items"]) == 2 and page["next_offset"] == 2
    assert client_for(other).get("/api/matches").json()["items"] == []
    assert set(page["items"][0]) == {
        "candidate_id", "display_name", "role", "verification_level", "city", "sector", "strength", "reason", "is_bridge",
    }  # fmt: skip
    assert client_for(seeker).get("/api/matches?limit=0").status_code == 422
