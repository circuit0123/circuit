"""Stage 6: the circuit endpoint returns everything the circuit screen and the completion moment need in ONE call
(DESIGN.md §4 Circuits): the three members with their yes and their done, who helps whom, time left, what to do next, ratings."""

import pytest

from apps.circuits.models import Circuit
from tests.api.test_circuits import make_loop
from tests.api.test_circuits import propose as propose_circuit

pytestmark = pytest.mark.django_db


@pytest.fixture
def ring(lists, make_member):
    asha, priya, arjun = make_loop(make_member)
    asha.display_name, priya.display_name, arjun.display_name = "Asha", "Priya", "Arjun"
    for m in (asha, priya, arjun):
        m.save()
    circuit = propose_circuit((asha, priya, arjun))
    return asha, priya, arjun, circuit


def get(client_for, member, circuit):
    r = client_for(member).get(f"/api/circuits/{circuit.pk}")
    assert r.status_code == 200
    return r.json()


def post(client_for, member, path, body=None):
    r = client_for(member).post(path, body or {})
    assert r.status_code == 200, r.content
    return r.json()


def accept_all(client_for, ring):
    *people, circuit = ring
    for m in people:
        post(client_for, m, f"/api/circuits/{circuit.pk}/respond", {"accept": True})


def my_leg(body, i_give=None, i_receive=None):
    return next(
        leg
        for leg in body["legs"]
        if (i_give is None or leg["i_give"] == i_give) and (i_receive is None or leg["i_receive"] == i_receive)
    )


def test_one_call_has_everything_the_screen_shows(ring, client_for):
    asha, priya, arjun, circuit = ring
    body = get(client_for, asha, circuit)
    assert set(body) == {
        "id", "status", "score_percent", "week", "consent_deadline", "time_left_seconds", "created_at", "my_consent",
        "next_step", "you_help", "helps_you", "members", "legs",
    }  # fmt: skip
    assert body["status"] == "proposed" and body["my_consent"] == "pending" and body["next_step"] == "answer"
    assert 0 < body["time_left_seconds"] <= 72 * 3600
    # "You help Arjun with hiring" / "Priya helps you with marketing": the lines of the closing moment, no second request
    assert (body["you_help"]["person"]["display_name"], body["you_help"]["capability"]) == ("Arjun", "Hiring and recruiting")
    assert (body["helps_you"]["person"]["display_name"], body["helps_you"]["capability"]) == ("Priya", "Brand marketing")
    # ring order: each member gives to the next one, and the last gives back to the first
    assert [(m["person"]["display_name"], m["is_me"], m["consent"], m["done"]) for m in body["members"]] == [
        ("Asha", True, "pending", False), ("Arjun", False, "pending", False), ("Priya", False, "pending", False)
    ]  # fmt: skip
    ring_ids = [m["person"]["id"] for m in body["members"]]
    gives_to = {leg["giver"]["id"]: leg["receiver"]["id"] for leg in body["legs"]}
    assert [gives_to[ring_ids[i]] for i in range(3)] == [ring_ids[1], ring_ids[2], ring_ids[0]]
    assert len(body["legs"]) == 3 and all(
        set(leg) >= {"giver", "receiver", "capability", "consent", "fulfilled", "rated", "rating", "can_mark_done", "can_rate"}
        for leg in body["legs"]
    )


def test_each_yes_lights_up_that_persons_segment_live(ring, client_for):
    asha, priya, arjun, circuit = ring
    post(client_for, priya, f"/api/circuits/{circuit.pk}/respond", {"accept": True})
    for viewer in (asha, priya, arjun):  # everyone sees the same ring
        states = {m["person"]["display_name"]: m["consent"] for m in get(client_for, viewer, circuit)["members"]}
        assert states == {"Asha": "pending", "Priya": "accepted", "Arjun": "pending"}
    assert get(client_for, priya, circuit)["next_step"] == "waiting" and get(client_for, asha, circuit)["next_step"] == "answer"


def test_when_all_three_say_yes_it_is_active_and_each_member_has_their_one_job(ring, client_for):
    asha, priya, arjun, circuit = ring
    accept_all(client_for, ring)
    body = get(client_for, asha, circuit)
    assert body["status"] == "active" and body["time_left_seconds"] is None and body["next_step"] == "mark_done"
    assert [leg["can_mark_done"] for leg in body["legs"] if leg["i_give"]] == [True]
    assert not any(leg["can_mark_done"] for leg in body["legs"] if not leg["i_give"])  # only my own handover
    assert not any(leg["can_rate"] for leg in body["legs"])  # nothing to rate yet


def test_done_then_rating_then_closed(ring, client_for):
    asha, priya, arjun, circuit = ring
    accept_all(client_for, ring)
    mine_to_arjun = my_leg(get(client_for, asha, circuit), i_give=True)
    after = post(client_for, asha, f"/api/circuits/{circuit.pk}/legs/{mine_to_arjun['id']}/done")
    assert after["next_step"] == "waiting" and {m["person"]["display_name"]: m["done"] for m in after["members"]}["Asha"] is True
    arjun_view = get(client_for, arjun, circuit)
    assert (
        my_leg(arjun_view, i_receive=True)["can_rate"] is True and arjun_view["next_step"] == "mark_done"
    )  # his own handover is still due
    rated = post(client_for, arjun, f"/api/circuits/{circuit.pk}/legs/{mine_to_arjun['id']}/rating", {"rating": 5})
    assert my_leg(rated, i_receive=True)["rating"] == 5 and my_leg(rated, i_receive=True)["can_rate"] is False
    for m in (priya, arjun):  # the other two hand over; the loop closes
        leg = my_leg(get(client_for, m, circuit), i_give=True)
        done = post(client_for, m, f"/api/circuits/{circuit.pk}/legs/{leg['id']}/done")
    assert done["status"] == "completed" and all(x["done"] for x in done["members"])
    assert Circuit.objects.get(pk=circuit.pk).status == "completed"
    # each person rates what they received: Asha and Priya still have to, Arjun already rated Asha's handover
    assert [get(client_for, m, circuit)["next_step"] for m in (asha, priya, arjun)] == ["rate", "rate", "none"]


def test_ratings_show_only_on_the_handovers_i_am_part_of(ring, client_for):
    asha, priya, arjun, circuit = ring
    accept_all(client_for, ring)
    leg = my_leg(get(client_for, asha, circuit), i_give=True)  # Asha gives to Arjun
    post(client_for, asha, f"/api/circuits/{circuit.pk}/legs/{leg['id']}/done")
    post(client_for, arjun, f"/api/circuits/{circuit.pk}/legs/{leg['id']}/rating", {"rating": 4})
    seen = {}
    for name, m in (("asha", asha), ("priya", priya), ("arjun", arjun)):
        row = next(x for x in get(client_for, m, circuit)["legs"] if x["id"] == leg["id"])
        seen[name] = (row["rated"], row["rating"])
    assert seen == {
        "asha": (True, 4),
        "arjun": (True, 4),
        "priya": (True, None),
    }  # the third member learns that it was rated, not how


def test_one_no_ends_it_for_everyone_and_the_screen_says_so(ring, client_for):
    asha, priya, arjun, circuit = ring
    post(client_for, arjun, f"/api/circuits/{circuit.pk}/respond", {"accept": False})
    for m in (asha, priya, arjun):
        body = get(client_for, m, circuit)
        assert body["status"] == "declined" and body["next_step"] == "none" and body["time_left_seconds"] is None
        assert not any(leg["can_mark_done"] or leg["can_rate"] for leg in body["legs"])


def test_an_expired_proposal_reads_as_expired_with_no_time_left(ring, client_for):
    from datetime import timedelta

    from django.utils import timezone

    asha, _, _, circuit = ring
    Circuit.objects.filter(pk=circuit.pk).update(consent_deadline=timezone.now() - timedelta(minutes=1))
    body = get(client_for, asha, circuit)
    assert body["status"] == "expired" and body["time_left_seconds"] is None and body["next_step"] == "none"


def test_the_list_returns_the_same_full_shape(ring, client_for):
    asha, _, _, circuit = ring
    [item] = client_for(asha).get("/api/circuits").json()["items"]
    assert item == get(client_for, asha, circuit)


def test_somebody_elses_circuit_does_not_exist(ring, make_member, client_for):
    *_, circuit = ring
    outsider = make_member("founder")
    assert client_for(outsider).get(f"/api/circuits/{circuit.pk}").status_code == 404
    assert client_for(outsider).get("/api/circuits").json()["items"] == []


def test_every_change_nudges_the_circuit_channel_with_an_id_only(
    ring, client_for, realtime_events, django_capture_on_commit_callbacks
):
    asha, priya, arjun, circuit = ring
    topic = f"circuit:{circuit.pk}"
    with django_capture_on_commit_callbacks(execute=True):
        accept_all(client_for, ring)
    leg = my_leg(get(client_for, asha, circuit), i_give=True)
    with django_capture_on_commit_callbacks(execute=True):
        post(client_for, asha, f"/api/circuits/{circuit.pk}/legs/{leg['id']}/done")
        post(client_for, arjun, f"/api/circuits/{circuit.pk}/legs/{leg['id']}/rating", {"rating": 5})
    nudges = [e for e in realtime_events if e[0] == topic]
    assert len(nudges) == 5 and all(e[1:] == ("status", {"circuit_id": circuit.pk}) for e in nudges)  # 3 yes, 1 done, 1 rating
    assert not any("Asha" in str(e) for e in realtime_events)
