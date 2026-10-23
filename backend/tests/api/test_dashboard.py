from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.intros.models import IntroRequest
from apps.matching.models import Capability, MatchResult, Need, Offer
from core.cache import get_cache

pytestmark = pytest.mark.django_db


@pytest.fixture
def org(make_org):
    return make_org("Kaveri Institute")


@pytest.fixture
def admin(make_member, org):
    return make_member("partner_admin", org=org)


def students(make_member, org, n, **kw):
    return [make_member("student", org=org, **kw) for _ in range(n)]


def need(m, slug="regulatory-affairs"):
    Need.objects.create(member=m, capability=Capability.objects.get(slug=slug), description="")


def offer(m, slug="regulatory-affairs"):
    Offer.objects.create(member=m, capability=Capability.objects.get(slug=slug), description="")


def get(client_for, who, path):
    r = client_for(who).get("/api/dashboard" + path)
    assert r.status_code == 200, r.content
    return r.json()


def row(gaps, slug):
    return next((g for g in gaps if g["capability"] == slug), None)


# -- who can look ------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/gaps", "/heatmap", "/network", "/acceptance"])
def test_only_a_partner_admin_with_an_organisation_can_look(path, admin, make_member, make_org, client_for):
    for role in ("student", "founder", "mentor", "investor", "super_admin"):
        assert client_for(make_member(role, org=admin.organisation)).get("/api/dashboard" + path).status_code == 403
    lonely = make_member("partner_admin")  # not appointed to an organisation
    assert client_for(lonely).get("/api/dashboard" + path).status_code == 403
    assert client_for(admin).get("/api/dashboard" + path).status_code == 200


# -- gaps --------------------------------------------------------------------------------------------------
def test_a_gap_shows_when_enough_members_need_what_nobody_in_the_organisation_offers(lists, admin, org, make_member, client_for):
    for s in students(make_member, org, 9):
        need(s)
    for _ in range(2):
        offer(make_member("mentor"))  # outside the organisation
    g = row(get(client_for, admin, "/gaps"), "regulatory-affairs")
    assert g["needed_by"] == {"value": 9, "hidden": False}
    assert g["offered_by"] == {"value": None, "hidden": True}  # zero is below 5, so it is not shown as a number
    assert g["offered_outside"]["hidden"] is True  # only 2 outside
    assert g["is_gap"] is True


def test_outside_supply_is_shown_once_it_is_five_or_more(lists, admin, org, make_member, client_for):
    for s in students(make_member, org, 6):
        need(s)
    for _ in range(5):
        offer(make_member("mentor"))
    assert row(get(client_for, admin, "/gaps"), "regulatory-affairs")["offered_outside"] == {"value": 5, "hidden": False}


def test_small_numbers_are_hidden_and_two_small_numbers_drop_the_row(lists, admin, org, make_member, client_for):
    for s in students(make_member, org, 4):
        need(s)
    assert row(get(client_for, admin, "/gaps"), "regulatory-affairs") is None
    get_cache().flush_prefix("dash:")
    for s in students(make_member, org, 6):
        offer(s)
    g = row(get(client_for, admin, "/gaps"), "regulatory-affairs")
    assert g["needed_by"]["hidden"] is True and g["offered_by"]["value"] == 6 and g["is_gap"] is False


def test_other_organisations_and_non_members_do_not_count(lists, admin, org, make_member, make_org, client_for):
    other = make_org("Other College")
    for s in students(make_member, other, 8):
        need(s)
    for s in students(make_member, None, 8):
        need(s)
    assert get(client_for, admin, "/gaps") == []
    assert row(get(client_for, make_member("partner_admin", org=other), "/gaps"), "regulatory-affairs")["needed_by"]["value"] == 8


def test_suspended_members_and_the_admin_are_not_counted(lists, admin, org, make_member, client_for):
    for s in students(make_member, org, 5):
        need(s)
    gone = make_member("student", org=org, suspended_at=timezone.now())
    need(gone)
    need(admin)
    assert row(get(client_for, admin, "/gaps"), "regulatory-affairs")["needed_by"]["value"] == 5


def test_biggest_gap_comes_first(lists, admin, org, make_member, client_for):
    ss = students(make_member, org, 10)
    for s in ss:
        need(s, "regulatory-affairs")
    for s in ss[:6]:
        need(s, "fundraising")
    slugs = [g["capability"] for g in get(client_for, admin, "/gaps")]
    assert slugs[:2] == ["regulatory-affairs", "fundraising"]


# -- heatmap -----------------------------------------------------------------------------------------------
def test_heatmap_leaves_out_cells_with_fewer_than_five_members(lists, admin, org, make_member, client_for):
    busy, quiet = Point(80.2200, 13.0100, srid=4326), Point(80.4000, 13.2000, srid=4326)
    for s in students(make_member, org, 5, location=busy):
        need(s)
    students(make_member, org, 4, location=quiet)
    out = get(client_for, admin, "/heatmap")
    assert len(out["cells"]) == 1 and out["cells"][0]["count"] == 5
    assert abs(out["cells"][0]["lat"] - 13.01) < 0.02 and abs(out["cells"][0]["lng"] - 80.22) < 0.02
    assert get(client_for, admin, "/heatmap?capability=regulatory-affairs")["cells"][0]["count"] == 5
    assert get(client_for, admin, "/heatmap?capability=fundraising")["cells"] == []


# -- network -----------------------------------------------------------------------------------------------
def test_network_numbers_and_hiding(lists, admin, org, make_member, client_for):
    ss = students(make_member, org, 6)
    out = get(client_for, admin, "/network")
    assert out["members"] == {"value": 6, "hidden": False}
    assert out["new_members_30d"]["value"] == 6
    assert out["intros_requested"] == {"value": None, "hidden": True}
    for s in ss[:5]:
        MatchResult.objects.create(member=s, candidate=ss[5], score=0.5, reason="x")
    get_cache().flush_prefix("dash:")
    assert get(client_for, admin, "/network")["members_with_matches"]["value"] == 5


def test_new_members_only_counts_the_last_30_days(lists, admin, org, make_member, client_for):
    ss = students(make_member, org, 7)
    from apps.accounts.models import Member

    Member.objects.filter(pk__in=[s.pk for s in ss[:3]]).update(created_at=timezone.now() - timedelta(days=60))
    assert get(client_for, admin, "/network")["new_members_30d"] == {"value": None, "hidden": True}  # 4 new: hidden


# -- acceptance --------------------------------------------------------------------------------------------
def intros(requester, targets, accepted):
    for i, t in enumerate(targets):
        IntroRequest.objects.create(
            requester=requester, target=t, expires_at=timezone.now() + timedelta(days=7),
            status="accepted" if i < accepted else "declined", stage="done",
        )  # fmt: skip


def test_acceptance_splits_local_and_bridge_and_hides_small_numbers(lists, admin, org, make_member, client_for):
    ss = students(make_member, org, 6)
    mentors = [make_member("mentor") for _ in range(12)]
    for s in ss:  # the bridge matches are flagged on the requester's MatchResult rows
        for m in mentors[:6]:
            MatchResult.objects.create(member=s, candidate=m, score=0.5, reason="x", is_bridge=True)
    intros(ss[0], mentors[:6], accepted=5)  # 6 bridge intros, 5 accepted
    intros(ss[1], mentors[6:9], accepted=1)  # 3 local intros
    out = get(client_for, admin, "/acceptance")
    assert out["bridge"] == {
        "requested": {"value": 6, "hidden": False},
        "accepted": {"value": 5, "hidden": False},
        "rate_percent": 83,
    }
    assert out["local"]["requested"]["hidden"] is True and out["local"]["rate_percent"] is None


def test_the_rate_is_hidden_when_the_accepted_count_is_small(lists, admin, org, make_member, client_for):
    ss = students(make_member, org, 6)
    mentors = [make_member("mentor") for _ in range(8)]
    intros(ss[0], mentors, accepted=2)
    out = get(client_for, admin, "/acceptance")["local"]
    assert out["requested"]["value"] == 8 and out["accepted"]["hidden"] is True and out["rate_percent"] is None


# -- caching and privacy -----------------------------------------------------------------------------------
def test_results_are_cached_for_a_few_minutes(lists, admin, org, make_member, client_for):
    for s in students(make_member, org, 5):
        need(s)
    assert len(get(client_for, admin, "/gaps")) == 1
    for s in students(make_member, org, 5):
        need(s, "fundraising")
    assert len(get(client_for, admin, "/gaps")) == 1  # still the cached answer
    get_cache().flush_prefix("dash:")
    assert len(get(client_for, admin, "/gaps")) == 2


def test_nothing_in_a_response_identifies_a_member(lists, admin, org, make_member, client_for):
    ss = students(make_member, org, 6, location=Point(80.22, 13.01, srid=4326))
    for s in ss:
        need(s)
    blob = "".join(
        client_for(admin).get("/api/dashboard" + p).content.decode() for p in ("/gaps", "/heatmap", "/network", "/acceptance")
    )
    for s in ss:
        assert s.display_name not in blob and f'"id": {s.pk}' not in blob
