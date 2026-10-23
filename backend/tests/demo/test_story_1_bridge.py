"""Demo story 1: a biotech startup needing marketing is matched with a deep-tech marketer as a Bridge match."""

import pytest

from tests.demo.conftest import person

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.story(1)]


def test_story_1_biotech_founder_gets_the_deeptech_marketer_as_a_bridge_match(seeded, client_for):
    kavya, rohan = person("kavya"), person("rohan")
    items = client_for(kavya).get("/api/matches?limit=100").json()["items"]
    row = next((r for r in items if r["candidate_id"] == rohan.pk), None)
    assert row is not None, "Rohan is not in Kavya's matches"
    assert row["is_bridge"] is True and row["sector"] == "deeptech"
    assert "marketing" in row["reason"].lower()
    assert "long sales cycle" in row["reason"] and "technical buyers" in row["reason"]
    assert items.index(row) < 5, f"Rohan only ranks {items.index(row) + 1}"


def test_story_1_works_from_the_other_side_and_the_bridge_filter_finds_it(seeded, client_for):
    kavya, rohan = person("kavya"), person("rohan")
    mine = client_for(rohan).get("/api/matches?bridge=true&limit=100").json()["items"]
    assert kavya.pk in {r["candidate_id"] for r in mine}
