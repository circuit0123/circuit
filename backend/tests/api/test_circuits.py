from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.circuits import services
from apps.circuits.models import Circuit, CircuitLeg, CircuitRound
from apps.events.models import Event
from apps.matching.models import Capability, Need, Offer
from apps.moderation.models import Block
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def want(m, slug):
    Need.objects.create(member=m, capability=Capability.objects.get(slug=slug), description="")


def give(m, slug):
    Offer.objects.create(member=m, capability=Capability.objects.get(slug=slug), description="")


def make_loop(make_member, **over):
    """Asha needs marketing, Priya needs fundraising, Arjun needs hiring; each offers what the next one needs."""
    asha, priya, arjun = (make_member("founder", circuits_opt_in=True, **over) for _ in range(3))
    want(asha, "brand-marketing"), give(asha, "recruiting")
    want(priya, "fundraising"), give(priya, "brand-marketing")
    want(arjun, "recruiting"), give(arjun, "fundraising")
    return asha, priya, arjun


@pytest.fixture
def loop(lists, make_member):
    return make_loop(make_member)


def kinds(m):
    return list(Notification.objects.filter(member=m).order_by("id").values_list("kind", flat=True))


def propose(loop):
    assert services.run_round()["circuits_created"] == 1
    return Circuit.objects.get()


def accept_all(circuit, client_for, loop):
    for m in loop:
        assert client_for(m).post(f"/api/circuits/{circuit.pk}/respond", {"accept": True}).status_code == 200


def leg_given_by(circuit, m):
    return CircuitLeg.objects.get(circuit=circuit, giver=m)


# -- the weekly round ---------------------------------------------------------------------------------
def test_round_proposes_the_loop(loop):
    asha, priya, arjun = loop
    summary = services.run_round(triggered_by="admin")
    assert summary["circuits_created"] == 1 and summary["loops_found"] == 1 and summary["edges"] == 3
    c = Circuit.objects.get()
    assert c.status == "proposed" and 0.2 <= c.score <= 1
    assert c.consent_deadline - timezone.now() > timedelta(hours=71)
    legs = {(leg.giver_id, leg.receiver_id): leg.capability.slug for leg in c.legs.select_related("capability")}
    assert legs == {
        (priya.pk, asha.pk): "brand-marketing", (arjun.pk, priya.pk): "fundraising", (asha.pk, arjun.pk): "recruiting",
    }  # fmt: skip
    assert all(kinds(m) == ["circuit.proposed"] for m in loop)
    assert CircuitRound.objects.get().status == "done" and CircuitRound.objects.get().triggered_by == "admin"
    assert (
        Event.objects.filter(type="circuit.proposed").count() == 1 and Event.objects.filter(type="circuit.round_run").count() == 1
    )


def test_running_the_round_again_changes_nothing(loop):
    services.run_round()
    again = services.run_round()
    assert again["circuits_created"] == 0 and Circuit.objects.count() == 1 and CircuitRound.objects.count() == 1
    assert all(kinds(m) == ["circuit.proposed"] for m in loop)  # nobody is notified twice


def test_a_second_loop_is_found_by_a_later_run(loop, make_member):
    services.run_round()
    second = make_loop(make_member)
    assert services.run_round()["circuits_created"] == 1
    assert Circuit.objects.count() == 2
    assert not set(m.pk for m in loop) & set(m.pk for m in second)


def test_members_who_did_not_opt_in_or_are_minors_are_left_out(lists, make_member):
    asha, priya, arjun = make_loop(make_member)
    arjun.circuits_opt_in = False
    arjun.save()
    assert services.run_round()["circuits_created"] == 0
    arjun.circuits_opt_in, arjun.is_minor = True, True
    arjun.save()
    assert services.run_round()["circuits_created"] == 0


def test_blocked_pairs_and_weak_loops_are_not_proposed(loop, settings):
    asha, priya, _ = loop
    Block.objects.create(blocker=asha, blocked=priya)
    assert services.run_round()["circuits_created"] == 0
    Block.objects.all().delete()
    settings.CIRCUIT_MIN_LEG_SCORE = 0.99
    assert services.run_round()["circuits_created"] == 0


def test_the_command_prints_a_summary(loop, capsys):
    call_command("run_circuit_round")
    assert "1 proposed" in capsys.readouterr().out


# -- consent -----------------------------------------------------------------------------------------------
def test_everyone_says_yes_and_it_goes_active(loop, client_for):
    c = propose(loop)
    asha, priya, arjun = loop
    first = client_for(asha).post(f"/api/circuits/{c.pk}/respond", {"accept": True}).json()
    assert first["status"] == "proposed" and first["my_consent"] == "accepted"
    client_for(priya).post(f"/api/circuits/{c.pk}/respond", {"accept": True})
    last = client_for(arjun).post(f"/api/circuits/{c.pk}/respond", {"accept": True}).json()
    assert last["status"] == "active" and {leg["consent"] for leg in last["legs"]} == {"accepted"}
    assert all(kinds(m)[-1] == "circuit.activated" for m in loop)
    assert Event.objects.filter(type="circuit.activated").count() == 1


def test_one_no_ends_it_for_everyone(loop, client_for):
    c = propose(loop)
    asha, priya, arjun = loop
    client_for(asha).post(f"/api/circuits/{c.pk}/respond", {"accept": True})
    assert client_for(priya).post(f"/api/circuits/{c.pk}/respond", {"accept": False}).json()["status"] == "declined"
    assert (
        kinds(asha)[-1] == "circuit.declined" and kinds(arjun)[-1] == "circuit.declined" and kinds(priya) == ["circuit.proposed"]
    )
    r = client_for(arjun).post(f"/api/circuits/{c.pk}/respond", {"accept": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "circuit_closed"
    # declined members are free for the next round
    assert services.run_round()["circuits_created"] == 1


def test_repeating_an_answer_is_safe_but_changing_it_is_not(loop, client_for):
    c = propose(loop)
    asha = loop[0]
    url = f"/api/circuits/{c.pk}/respond"
    assert client_for(asha).post(url, {"accept": True}).status_code == 200
    assert client_for(asha).post(url, {"accept": True}).status_code == 200
    r = client_for(asha).post(url, {"accept": False})
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_answered"
    assert Event.objects.filter(type="circuit.accepted").count() == 1


def test_outsiders_cannot_see_or_answer_a_circuit(loop, make_member, client_for):
    c = propose(loop)
    stranger = make_member("founder")
    sc = client_for(stranger)
    assert sc.get(f"/api/circuits/{c.pk}").status_code == 404
    assert sc.post(f"/api/circuits/{c.pk}/respond", {"accept": True}).status_code == 404
    assert sc.get("/api/circuits").json()["items"] == []


def test_a_proposal_that_runs_out_of_time_expires(loop, client_for, capsys):
    c = propose(loop)
    asha = loop[0]
    Circuit.objects.update(consent_deadline=timezone.now() - timedelta(minutes=1))
    assert client_for(asha).get("/api/circuits").json()["items"][0]["status"] == "expired"  # reads see it at once
    r = client_for(asha).post(f"/api/circuits/{c.pk}/respond", {"accept": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "circuit_expired"
    assert Circuit.objects.get().status == "expired" and kinds(asha)[-1] == "circuit.expired"


def test_expire_items_expires_old_proposals_once(loop, capsys):
    propose(loop)
    Circuit.objects.update(consent_deadline=timezone.now() - timedelta(minutes=1))
    call_command("expire_items")
    call_command("expire_items")
    out = capsys.readouterr().out
    assert "circuits expired: 1" in out and "circuits expired: 0" in out
    assert all(kinds(m).count("circuit.expired") == 1 for m in loop)


# -- handing over and rating -------------------------------------------------------------------------------------
def test_full_exchange_to_completion(loop, client_for):
    c = propose(loop)
    asha, priya, arjun = loop
    accept_all(c, client_for, loop)
    for giver in (priya, arjun, asha):
        leg = leg_given_by(c, giver)
        body = client_for(giver).post(f"/api/circuits/{c.pk}/legs/{leg.pk}/done").json()
        assert next(x for x in body["legs"] if x["id"] == leg.pk)["fulfilled"] is True
    assert Circuit.objects.get().status == "completed"
    assert all(kinds(m)[-1] == "circuit.completed" for m in loop)
    leg = leg_given_by(c, priya)  # Priya gave marketing to Asha, so Asha rates it
    body = client_for(asha).post(f"/api/circuits/{c.pk}/legs/{leg.pk}/rating", {"rating": 5}).json()
    assert next(x for x in body["legs"] if x["id"] == leg.pk)["rating"] == 5
    assert client_for(asha).post(f"/api/circuits/{c.pk}/legs/{leg.pk}/rating", {"rating": 1}).status_code == 200
    assert CircuitLeg.objects.get(pk=leg.pk).rating == 5  # the first rating stands


def test_done_and_rating_rules(loop, make_member, client_for):
    c = propose(loop)
    asha, priya, arjun = loop
    leg = leg_given_by(c, priya)
    done_url, rate_url = f"/api/circuits/{c.pk}/legs/{leg.pk}/done", f"/api/circuits/{c.pk}/legs/{leg.pk}/rating"
    r = client_for(priya).post(done_url)
    assert r.status_code == 409 and r.json()["error"]["code"] == "circuit_not_active"
    accept_all(c, client_for, loop)
    assert client_for(asha).post(done_url).status_code == 403  # only the giver marks it done
    assert client_for(make_member("founder")).post(done_url).status_code == 404
    r = client_for(asha).post(rate_url, {"rating": 4})
    assert r.status_code == 409 and r.json()["error"]["code"] == "leg_not_done"
    assert client_for(priya).post(done_url).status_code == 200
    assert client_for(priya).post(done_url).status_code == 200  # safe to repeat
    assert Event.objects.filter(type="circuit.leg_done").count() == 1
    assert client_for(priya).post(rate_url, {"rating": 4}).status_code == 403  # you cannot rate your own gift
    assert client_for(asha).post(rate_url, {"rating": 0}).status_code == 422
    assert client_for(asha).post(rate_url, {"rating": 4}).status_code == 200
    other = leg_given_by(c, arjun)
    assert client_for(asha).post(f"/api/circuits/{c.pk}/legs/{other.pk}/done").status_code == 403  # not hers to give


def test_a_leg_from_another_circuit_is_a_404(loop, lists, make_member, client_for):
    c = propose(loop)
    second = make_loop(make_member)
    services.run_round()
    other_circuit = Circuit.objects.exclude(pk=c.pk).get()
    foreign_leg = leg_given_by(other_circuit, second[0])
    assert client_for(loop[0]).post(f"/api/circuits/{c.pk}/legs/{foreign_leg.pk}/done").status_code == 404


def test_list_and_detail_show_live_status(loop, client_for):
    c = propose(loop)
    asha = loop[0]
    page = client_for(asha).get("/api/circuits").json()
    assert page["count"] == 1
    item = page["items"][0]
    assert item["id"] == c.pk and len(item["legs"]) == 3 and item["my_consent"] == "pending" and item["week"]
    assert sum(leg["i_give"] for leg in item["legs"]) == 1 and sum(leg["i_receive"] for leg in item["legs"]) == 1
    assert client_for(asha).get(f"/api/circuits/{c.pk}").json() == item
