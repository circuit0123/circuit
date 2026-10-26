"""B7 part 1: organisation search and the city list (sign-up steps 7 and 11)."""

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_org(db):
    from apps.organisations.models import Organisation
    from apps.organisations.services import generate_join_code

    def _make(name, kind="college", city="Chennai", email_domains=None):
        return Organisation.objects.create(
            name=name, kind=kind, city=city, email_domains=email_domains or [], join_code=generate_join_code()
        )

    return _make


# -- organisation search -------------------------------------------------------------------------------
def test_search_finds_organisations_by_name_best_first(make_member, make_org, client_for):
    make_org(name="Sri Venkateswara College of Engineering", city="Chennai")
    make_org(name="SVIT Chennai", city="Chennai")
    make_org(name="Bay of Bengal Incubator", city="Chennai")
    r = client_for(make_member()).get("/api/organisations/search", {"q": "sv"})
    assert r.status_code == 200
    assert [o["name"] for o in r.json()] == ["SVIT Chennai"]  # "sv" is contained once: the other name has no "sv" substring
    r = client_for(make_member()).get("/api/organisations/search", {"q": "ven"})
    assert [o["name"] for o in r.json()] == ["Sri Venkateswara College of Engineering"]


def test_names_that_start_with_the_text_come_first(make_member, make_org, client_for):
    make_org(name="Anna Tech Park")
    make_org(name="Tech Anna Institute")
    names = [o["name"] for o in client_for(make_member()).get("/api/organisations/search", {"q": "anna"}).json()]
    assert names == ["Anna Tech Park", "Tech Anna Institute"]


def test_search_never_shows_codes_or_domains(make_member, make_org, client_for):
    org = make_org(name="Coimbatore Institute", email_domains=["cit.edu.in"])
    body = client_for(make_member()).get("/api/organisations/search", {"q": "coim"}).content.decode()
    assert org.join_code not in body and "cit.edu.in" not in body and "join_code" not in body


def test_search_filters_by_kind_and_caps_the_list(make_member, make_org, client_for):
    for i in range(12):
        make_org(name=f"Delta College {i}", kind="college")
    make_org(name="Delta Labs", kind="incubator")
    c = client_for(make_member())
    assert len(c.get("/api/organisations/search", {"q": "delta"}).json()) == 10
    assert [o["name"] for o in c.get("/api/organisations/search", {"q": "delta", "kind": "incubator"}).json()] == ["Delta Labs"]


def test_search_needs_two_characters_and_a_known_kind(make_member, client_for):
    c = client_for(make_member())
    assert c.get("/api/organisations/search", {"q": "a"}).status_code == 422
    assert c.get("/api/organisations/search", {"q": "ab", "kind": "bank"}).status_code == 422
    assert c.get("/api/organisations/search").status_code == 422


def test_searching_does_not_join_anything(make_member, make_org, client_for):
    make_org(name="Open College")
    m = make_member()
    client_for(m).get("/api/organisations/search", {"q": "open"})
    m.refresh_from_db()
    assert m.organisation_id is None


def test_search_is_rate_limited_and_needs_sign_in(make_member, make_org, client_for, client, settings):
    make_org(name="Rate College")
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "org_search": (2, 3600)}
    c = client_for(make_member())
    assert [c.get("/api/organisations/search", {"q": "rate"}).status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/api/organisations/search", {"q": "rate"}).status_code == 401


# -- cities --------------------------------------------------------------------------------------------
def test_cities_start_with_the_pilot_city(make_member, client_for, settings):
    settings.SEED_CITY = {"name": "Coimbatore", "lat": 11.0, "lng": 76.9}
    body = client_for(make_member()).get("/api/cities").json()
    assert body[0] == {"name": "Coimbatore", "lat": 11.0, "lng": 76.9, "pilot": True}
    assert [c["name"] for c in body].count("Coimbatore") == 1 and all(not c["pilot"] for c in body[1:])
    assert len(body) > 20 and all(-90 <= c["lat"] <= 90 and -180 <= c["lng"] <= 180 for c in body)


def test_an_unlisted_pilot_city_is_still_first(make_member, client_for, settings):
    settings.SEED_CITY = {"name": "Tinyville", "lat": 10.0, "lng": 78.0}
    assert client_for(make_member()).get("/api/cities").json()[0]["name"] == "Tinyville"


def test_cities_need_sign_in(client):
    assert client.get("/api/cities").status_code == 401
