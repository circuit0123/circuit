"""B7 part 1: notification lines name the people and things involved ("Meera accepted your intro request to Sakthi.")."""

import pytest

from apps.accounts.models import Connection
from apps.notifications.services import notify

pytestmark = pytest.mark.django_db


def connect(x, y):
    Connection.objects.create(member_a_id=min(x.pk, y.pk), member_b_id=max(x.pk, y.pk), strength=0.9)


@pytest.fixture
def trio(make_member):
    asker, broker, target = (
        make_member("founder", display_name="Sneha"),
        make_member("mentor", display_name="Meera"),
        make_member("investor", display_name="Sakthi"),
    )
    connect(asker, broker)
    connect(broker, target)
    return asker, broker, target


def lines(client):
    return [n["text"] for n in client.get("/api/notifications").json()["items"]]


def test_the_requester_hears_who_vouched_and_for_whom(trio, client_for):
    asker, broker, target = trio
    r = client_for(asker).post("/api/intros", {"target_id": target.pk, "message": ""}).json()
    assert "Meera asked you" not in lines(client_for(broker))[0]
    assert lines(client_for(broker)) == ["Sneha asked you to vouch for an intro to Sakthi."]
    client_for(broker).post(f"/api/intros/{r['id']}/respond", {"accept": True})
    assert lines(client_for(asker)) == ["Meera vouched for your intro request to Sakthi."]
    assert lines(client_for(target)) == ["Sneha would like to meet you, vouched for by Meera."]
    client_for(target).post(f"/api/intros/{r['id']}/respond", {"accept": True})
    assert lines(client_for(asker))[0] == "Sakthi accepted your introduction."  # the person said yes themselves
    assert lines(client_for(broker))[0] == "Sakthi accepted the intro request from Sneha that you vouched for."


def test_a_direct_intro_has_no_vouching_clause(make_member, client_for):
    a, b = make_member("founder", display_name="Ann"), make_member("mentor", display_name="Bo")
    connect(a, b)
    client_for(a).post("/api/intros", {"target_id": b.pk, "message": ""})
    assert lines(client_for(b)) == ["Ann would like to meet you."]


def test_a_deleted_or_under_18_name_is_never_used(trio, client_for):
    asker, broker, target = trio
    client_for(asker).post("/api/intros", {"target_id": target.pk, "message": ""})
    target.deleted_at = target.updated_at
    target.save(update_fields=["deleted_at"])
    assert lines(client_for(broker)) == ["Sneha asked you to vouch for an introduction."]  # falls back to the plain line


def test_a_decline_still_does_not_say_who(trio, client_for):
    asker, broker, target = trio
    r = client_for(asker).post("/api/intros", {"target_id": target.pk, "message": ""}).json()
    client_for(broker).post(f"/api/intros/{r['id']}/respond", {"accept": False})
    assert lines(client_for(asker))[0] == "Your introduction request was declined."


def test_application_lines_name_the_role(make_member, make_startup, client_for):
    from apps.jobs.models import Job

    founder, student = make_member("founder"), make_member("student", display_name="Ravi")
    startup = make_startup(name="Acme", claimed_by=founder)
    job = Job.objects.create(startup=startup, title="Frontend intern", kind="internship")
    notify(founder, "application.received", actor=student, application_id=1, job_id=job.pk, startup_id=startup.pk)
    notify(student, "application.status", actor=founder, application_id=1, job_id=job.pk, status="shortlisted")
    notify(student, "application.status", actor=founder, application_id=1, job_id=job.pk, status="rejected")
    assert lines(client_for(founder)) == ["Ravi applied for Frontend intern."]
    assert lines(client_for(student)) == [
        "Your application for Frontend intern was not selected.",
        "You were shortlisted for Frontend intern.",
    ]


def test_an_unknown_status_or_missing_role_falls_back_to_the_plain_line(make_member, client_for):
    m = make_member("student")
    notify(m, "application.status", application_id=1, job_id=999999, status="applied")
    assert lines(client_for(m)) == ["Your application has a new status."]


def test_startup_lines_name_the_startup(make_member, make_startup, client_for):
    founder = make_member("founder")
    s = make_startup(name="Acme", claimed_by=founder)
    notify(founder, "startup.interest", startup_id=s.pk)
    assert lines(client_for(founder)) == ["Someone showed interest in Acme."]


def test_circuit_leg_lines_name_the_capability(make_member, lists, client_for):
    from datetime import timedelta

    from django.utils import timezone

    from apps.circuits.models import Circuit, CircuitLeg, CircuitRound
    from apps.matching.models import Capability

    a, b = make_member("student", display_name="Asha"), make_member("founder")
    rnd = CircuitRound.objects.create(week="2026-W40")
    circuit = Circuit.objects.create(round=rnd, status="active", score=0.8, consent_deadline=timezone.now() + timedelta(days=3))
    cap = Capability.objects.first()
    leg = CircuitLeg.objects.create(circuit=circuit, giver=a, receiver=b, capability=cap)
    notify(b, "circuit.leg_done", actor=a, circuit_id=circuit.pk, leg_id=leg.pk)
    assert lines(client_for(b)) == [f"Asha marked their help with {cap.name} as done."]


def test_a_page_of_notifications_costs_a_fixed_number_of_queries(
    make_member, make_startup, client_for, django_assert_max_num_queries
):
    m = make_member("founder")
    s = make_startup(claimed_by=m)
    for _ in range(25):
        notify(m, "startup.interest", startup_id=s.pk)
    c = client_for(m)
    c.get("/api/notifications")  # warm caches
    with django_assert_max_num_queries(14):
        assert len(c.get("/api/notifications?limit=25").json()["items"]) == 25
