"""Demo story 5: the partner college's cohort needs regulatory help, nobody in the college offers it, and the dashboard shows it."""

import pytest

from tests.demo.conftest import person

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.story(5)]


def test_story_5_the_partner_dashboard_shows_the_regulatory_gap(seeded, client_for):
    meenakshi = person("meenakshi")
    gaps = client_for(meenakshi).get("/api/dashboard/gaps").json()
    reg = next(g for g in gaps if g["capability"] == "regulatory-affairs")
    assert reg["needed_by"]["hidden"] is False and reg["needed_by"]["value"] >= 5
    assert reg["offered_by"]["hidden"] is True  # nobody (fewer than 5) inside the college offers it
    assert reg["is_gap"] is True


def test_story_5_small_numbers_stay_hidden_and_students_cannot_look(seeded, client_for):
    meenakshi, ravi = person("meenakshi"), person("ravi")
    net = client_for(meenakshi).get("/api/dashboard/network").json()
    assert net["members"]["hidden"] is False
    assert all(v["value"] is None or v["value"] >= 5 for v in net.values())
    assert client_for(ravi).get("/api/dashboard/gaps").status_code == 403
