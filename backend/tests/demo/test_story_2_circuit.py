"""Demo story 2: Asha needs marketing, Priya needs fundraising, Arjun needs hiring - and each can give what the next needs."""

import pytest

from apps.circuits import services
from apps.circuits.models import Circuit, CircuitLeg
from tests.demo.conftest import person

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.story(2)]


def test_story_2_the_round_proposes_the_loop_and_it_runs_to_completion(seeded, client_for):
    asha, priya, arjun = person("asha"), person("priya"), person("arjun")
    assert services.run_round()["circuits_created"] == 1
    circuit = Circuit.objects.get()
    legs = {(leg.giver_id, leg.receiver_id): leg.capability.slug for leg in circuit.legs.select_related("capability")}
    assert legs == {
        (priya.pk, asha.pk): "brand-marketing", (arjun.pk, priya.pk): "fundraising", (asha.pk, arjun.pk): "recruiting",
    }  # fmt: skip

    for m in (asha, priya, arjun):  # everyone says yes within the 72 hours
        assert client_for(m).post(f"/api/circuits/{circuit.pk}/respond", {"accept": True}).status_code == 200
    assert client_for(asha).get(f"/api/circuits/{circuit.pk}").json()["status"] == "active"

    for giver in (priya, arjun, asha):  # each hands over what they promised
        leg = CircuitLeg.objects.get(circuit=circuit, giver=giver)
        assert client_for(giver).post(f"/api/circuits/{circuit.pk}/legs/{leg.pk}/done").status_code == 200
    body = client_for(asha).get(f"/api/circuits/{circuit.pk}").json()
    assert body["status"] == "completed"

    for leg in CircuitLeg.objects.filter(circuit=circuit):  # and each receiver rates it
        r = client_for(leg.receiver).post(f"/api/circuits/{circuit.pk}/legs/{leg.pk}/rating", {"rating": 5})
        assert r.status_code == 200
    assert set(CircuitLeg.objects.filter(circuit=circuit).values_list("rating", flat=True)) == {5}


def test_story_2_running_the_round_again_does_not_duplicate_it(seeded):
    services.run_round()
    assert services.run_round()["circuits_created"] == 0 and Circuit.objects.count() == 1
