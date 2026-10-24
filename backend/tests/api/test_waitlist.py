"""POST /api/waitlist: public, rate limited per address, the same answer for a repeat, no personal data in logs."""

import json

import pytest
from django.test import Client

from apps.beta.models import WaitlistEntry
from apps.events.models import Event

pytestmark = pytest.mark.django_db
URL = "/api/waitlist"
BODY = {
    "email": "Asha.Waits@Example.org",
    "role": "student",
    "city": "Chennai",
    "college": "KIT College",
    "note": "Need a first internship",
    "src": "landing-students",
}


def post(body=None, client=None, **extra):
    return (client or Client()).post(URL, json.dumps(body or BODY), content_type="application/json", **extra)


def test_joining_needs_no_account_and_answers_202():
    r = post()
    assert r.status_code == 202 and r.json() == {"status": "ok"}
    e = WaitlistEntry.objects.get()
    assert (e.email, e.role, e.city, e.college, e.src, e.status) == (
        "asha.waits@example.org",
        "student",
        "Chennai",
        "KIT College",
        "landing-students",
        "pending",
    )
    ev = Event.objects.get(type="waitlist.joined")
    assert ev.payload == {"role": "student", "src": "landing-students"}  # no email in the event


def test_a_repeat_looks_exactly_like_the_first_time():
    first, again = post(), post({**BODY, "role": "founder", "note": "changed"})
    other_case = post({**BODY, "email": "ASHA.WAITS@EXAMPLE.ORG"})
    assert (
        (first.status_code, first.content) == (again.status_code, again.content) == (other_case.status_code, other_case.content)
    )
    assert WaitlistEntry.objects.count() == 1
    assert WaitlistEntry.objects.get().role == "student"  # the first answer stands
    assert Event.objects.filter(type="waitlist.joined").count() == 1


def test_a_repeat_after_approval_or_rejection_also_looks_the_same():
    post()
    WaitlistEntry.objects.update(status="approved")
    assert post().json() == {"status": "ok"}
    assert WaitlistEntry.objects.get().status == "approved"


@pytest.mark.parametrize(
    "patch",
    [
        {"email": "not-an-email"},
        {"email": "a@b"},
        {"email": "Kim@example.org"},
        {"email": '"quoted"@example.org'},
        {"email": "x" * 300 + "@example.org"},
        {"role": "super_admin"},
        {"role": ""},
        {"note": "x" * 501},
        {"src": "Landing Students!"},
        {"city": "c" * 101},
    ],
)
def test_bad_input_is_rejected_and_stores_nothing(patch):
    r = post({**BODY, **patch})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert not WaitlistEntry.objects.exists()


def test_optional_fields_may_be_left_out():
    assert post({"email": "min@example.org", "role": "mentor"}).status_code == 202
    assert WaitlistEntry.objects.get().city == ""


def test_works_with_or_without_a_token(client_for, make_member):
    assert post(client=client_for(make_member("student"))).status_code == 202
    assert post({**BODY, "email": "b@example.org"}, client=Client(HTTP_AUTHORIZATION="Bearer junk")).status_code == 202


def test_rate_limited_per_address(settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "waitlist": (3, 3600)}
    statuses = [post({**BODY, "email": f"p{i}@example.org"}, REMOTE_ADDR="198.51.100.1").status_code for i in range(5)]
    assert statuses == [202, 202, 202, 429, 429]
    assert WaitlistEntry.objects.count() == 3
    assert post({**BODY, "email": "other@example.org"}, REMOTE_ADDR="198.51.100.2").status_code == 202
    assert post({**BODY, "email": "p9@example.org"}, REMOTE_ADDR="198.51.100.1").json()["error"]["code"] == "rate_limited"


def test_a_repeat_counts_against_the_limit_too(settings):
    """Otherwise the quickest way to learn whether an email is on the list would be a free, unlimited probe."""
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "waitlist": (2, 3600)}
    assert [post().status_code for _ in range(3)] == [202, 202, 429]


# -- CORS: the landing site may call this one path ------------------------------------------------------
def test_landing_origin_may_call_the_waitlist_only(settings):
    settings.LANDING_URL = "https://landing.example/"
    r = post(HTTP_ORIGIN="https://landing.example")
    assert r.headers["Access-Control-Allow-Origin"] == "https://landing.example"
    pre = Client().options(URL, HTTP_ORIGIN="https://landing.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert pre.headers["Access-Control-Allow-Origin"] == "https://landing.example"
    other = Client().get("/api/config", HTTP_ORIGIN="https://landing.example")
    assert "Access-Control-Allow-Origin" not in other.headers  # nothing else is open to the landing site
    me = Client().options("/api/me", HTTP_ORIGIN="https://landing.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET")
    assert "Access-Control-Allow-Origin" not in me.headers


def test_a_stranger_origin_is_not_allowed_on_the_waitlist(settings):
    settings.LANDING_URL = "https://landing.example"
    for origin in ("https://evil.example", "https://landing.example.evil.example", "http://landing.example"):
        assert "Access-Control-Allow-Origin" not in post(HTTP_ORIGIN=origin).headers


# -- privacy ------------------------------------------------------------------------------------
def test_no_name_email_or_address_reaches_the_logs(capfd, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "waitlist": (1, 3600)}
    post({**BODY, "note": "A very private note", "college": "Secret College"}, REMOTE_ADDR="198.51.100.77")
    post(REMOTE_ADDR="198.51.100.77")  # repeat, and the 429 path
    post({**BODY, "email": "bad"}, REMOTE_ADDR="198.51.100.78")  # validation path
    out = capfd.readouterr().out
    assert out and '"event": "request"' in out
    for secret in (
        "asha.waits",
        "Asha.Waits",
        "example.org",
        "A very private note",
        "Secret College",
        "KIT College",
        "198.51.100.77",
        "198.51.100.78",
    ):
        assert secret not in out, f"{secret!r} leaked into logs"
