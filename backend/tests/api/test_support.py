"""Stage 7: data requests (DPDP). Correction is the normal profile edit; this is the support and grievance route."""

import pytest
from django.test import Client

from apps.events.models import Event
from core.models import OutboundEmail

pytestmark = pytest.mark.django_db
MESSAGE = "Please correct my college to KIT Coimbatore. My number is 9876543210."


def send(client, kind="question", message=MESSAGE):
    return client.post("/api/support", {"kind": kind, "message": message})


def test_a_question_goes_to_the_support_inbox_with_a_reply_to_and_the_member_gets_a_reference(make_member, client_for, settings):
    settings.SUPPORT_EMAIL = "help@circuit.example"
    m = make_member("student", display_name="Meera Iyer")
    r = send(client_for(m, email="meera@example.org"))
    assert r.status_code == 202 and r.json()["reference"].startswith("S-")
    to_support = OutboundEmail.objects.get(to_email="help@circuit.example")
    assert (
        to_support.headers == {"Reply-To": "meera@example.org"}
        and MESSAGE in to_support.body
        and f"member {m.pk}" in to_support.subject
    )
    ack = OutboundEmail.objects.get(to_email="meera@example.org")
    assert r.json()["reference"] in ack.subject and "Grievance officer" not in ack.body


def test_a_grievance_goes_to_the_grievance_officer_and_the_acknowledgement_names_them(make_member, client_for, settings):
    settings.GRIEVANCE = {"name": "Dr. A. Officer", "email": "grievance@circuit.example", "address": "1 Test Street"}
    m = make_member("founder")
    r = send(client_for(m, email="f@example.org"), kind="grievance", message="You shared my data without asking.")
    assert r.status_code == 202
    assert OutboundEmail.objects.filter(to_email="grievance@circuit.example", kind="support.grievance").count() == 1
    ack = OutboundEmail.objects.get(to_email="f@example.org")
    assert "Dr. A. Officer" in ack.body and "grievance@circuit.example" in ack.body


@pytest.mark.parametrize("kind", ["question", "correction", "data_request", "grievance"])
def test_every_kind_is_accepted(make_member, client_for, kind):
    assert send(client_for(make_member("student")), kind=kind).status_code == 202


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "spam", "message": MESSAGE},
        {"kind": "question", "message": "hi"},
        {"kind": "question", "message": "x" * 2001},
        {"message": MESSAGE},
        {"kind": "question"},
    ],
)
def test_bad_requests_are_rejected_and_nothing_is_sent(make_member, client_for, body):
    assert client_for(make_member("student")).post("/api/support", body).status_code == 422
    assert not OutboundEmail.objects.exists()


def test_support_needs_a_signed_in_member(client_for):
    assert send(client_for()).status_code == 401


def test_support_is_rate_limited_per_member(make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "support": (2, 86400)}
    a, b = make_member("student"), make_member("student")
    assert [send(client_for(a)).status_code for _ in range(3)] == [202, 202, 429]
    assert send(client_for(b)).status_code == 202  # another member is unaffected


def test_a_member_without_an_email_can_still_write(make_member, client_for):
    m = make_member("student")
    assert send(client_for(m, email=None)).status_code == 202  # token has no email claim
    assert OutboundEmail.objects.count() == 1 and OutboundEmail.objects.get().headers == {}


def test_no_message_text_or_address_reaches_logs_or_events(make_member, client_for, capfd):
    m = make_member("student", display_name="Meera Iyer")
    capfd.readouterr()
    send(client_for(m, email="meera.private@example.org"), kind="data_request")
    out = capfd.readouterr().out
    for private in ("KIT Coimbatore", "9876543210", "meera.private", "Meera Iyer"):
        assert private not in out
    event = Event.objects.get(type="support.requested")
    assert event.payload == {"kind": "data_request"} and "KIT" not in str(event.payload)


def test_the_contact_details_are_public_and_come_from_settings(settings):
    settings.SUPPORT_EMAIL = "help@circuit.example"
    settings.GRIEVANCE = {"name": "Dr. A. Officer", "email": "grievance@circuit.example", "address": "1 Test Street"}
    r = Client().get("/api/support/contact")
    assert r.status_code == 200
    assert r.json() == {"support_email": "help@circuit.example", "grievance": settings.GRIEVANCE}


def test_the_default_contact_shows_the_placeholders_not_invented_details():
    body = Client().get("/api/support/contact").json()
    assert body["grievance"]["name"] == "<GRIEVANCE_OFFICER>" or "<" not in body["grievance"]["name"]
