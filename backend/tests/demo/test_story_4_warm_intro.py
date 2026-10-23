"""Demo story 4: Sneha reaches investor Vikram through the mentor they both know (Lakshmi); they have no direct link."""

import pytest

from apps.accounts.models import Connection
from tests.demo.conftest import person

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.story(4)]


def test_story_4_the_intro_goes_through_lakshmi(seeded, client_for):
    sneha, lakshmi, vikram = person("sneha"), person("lakshmi"), person("vikram")
    a, b = sorted((sneha.pk, vikram.pk))
    assert not Connection.objects.filter(member_a_id=a, member_b_id=b).exists()

    sc, lc, vc = client_for(sneha), client_for(lakshmi), client_for(vikram)
    path = sc.get(f"/api/intros/path/{vikram.pk}").json()
    assert path["via"]["id"] == lakshmi.pk and path["via"]["verification_level"] == 3

    intro = sc.post("/api/intros", {"target_id": vikram.pk, "message": "We are raising a seed round for clean-tech sensors."})
    assert intro.status_code == 201
    intro_id = intro.json()["id"]
    assert vc.get("/api/intros?box=received").json()["items"] == []  # Vikram hears nothing until Lakshmi vouches

    waiting = lc.get("/api/intros?box=brokered").json()["items"][0]
    assert waiting["can_respond"] is True and waiting["requester"]["id"] == sneha.pk
    assert lc.post(f"/api/intros/{intro_id}/respond", {"accept": True}).json()["stage"] == "target"

    inbox = vc.get("/api/intros?box=received").json()["items"][0]
    assert inbox["id"] == intro_id and inbox["via"]["id"] == lakshmi.pk
    assert vc.post(f"/api/intros/{intro_id}/respond", {"accept": True}).json()["status"] == "accepted"

    done = sc.post(f"/api/intros/{intro_id}/rating", {"rating": 5}).json()
    assert done["status"] == "completed" and done["outcome_rating"] == 5
