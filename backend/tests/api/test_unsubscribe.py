"""Stage 6: the one-click unsubscribe link in every notification email. Works signed out; only switches off that email type."""

import time

import pytest
from django.core import signing
from django.test import Client
from django.utils import timezone

from apps.events.models import Event
from apps.notifications import prefs, unsubscribe
from apps.notifications.services import notify
from core.models import OutboundEmail

pytestmark = pytest.mark.django_db


def link_token(member, type_="intros"):
    return unsubscribe.make_token(member.pk, type_)


def post(token, **extra):
    return Client().post(f"/api/unsubscribe?token={token}", **extra)  # no Authorization header: signed out


def test_the_link_in_a_real_email_works_once_signed_out(make_member):
    m = make_member("student", email="reader@example.org")
    notify(m, "intro.received", intro_id=1)
    token = OutboundEmail.objects.get().headers["List-Unsubscribe"].split("token=")[1].rstrip(">")
    r = post(token)
    assert r.status_code == 200 and r.json() == {"type": "intros", "label": "introductions", "email_on": False}
    m.refresh_from_db()
    assert prefs.resolved(m)["intros"] == {"in_app": True, "email": False, "push": True}  # only the email channel changed
    assert Event.objects.filter(actor=m, type="email.unsubscribed", payload__notification_type="intros").count() == 1


def test_only_that_type_is_switched_off(make_member):
    m = make_member("student")
    post(link_token(m, "intros"))
    m.refresh_from_db()
    resolved = prefs.resolved(m)
    assert resolved["intros"]["email"] is False
    assert resolved["applications"] == {"in_app": True, "email": True, "push": True}
    assert resolved["circuits"] == {"in_app": True, "email": True, "push": True}


def test_it_is_safe_to_click_twice(make_member):
    m = make_member("student")
    assert post(link_token(m)).status_code == 200
    assert post(link_token(m)).json()["email_on"] is False
    assert Event.objects.filter(type="email.unsubscribed").count() == 1  # the second click changed nothing


def test_opening_the_link_changes_nothing_so_mail_scanners_are_harmless(make_member):
    m = make_member("student")
    r = Client().get(f"/api/unsubscribe?token={link_token(m)}")
    assert r.status_code == 200 and r.json() == {"type": "intros", "label": "introductions", "email_on": True}
    m.refresh_from_db()
    assert m.notification_prefs == {}


def test_the_one_click_post_from_a_mail_client_works(make_member):
    """RFC 8058: the mail app POSTs `List-Unsubscribe=One-Click` as a form body to the URL in the header."""
    m = make_member("student")
    r = post(link_token(m), data="List-Unsubscribe=One-Click", content_type="application/x-www-form-urlencoded")
    assert r.status_code == 200 and r.json()["email_on"] is False


def test_a_tampered_token_is_rejected(make_member):
    m, other = make_member("student"), make_member("student")
    good = link_token(m)
    flipped = good[:-1] + ("A" if good[-1] != "A" else "B")
    for bad in (flipped, good + "x", "x" * 20, "", "not-a-token", link_token(other).split(":")[0] + ":" + good.split(":", 1)[1]):
        r = post(bad)
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_token", bad
    m.refresh_from_db()
    assert m.notification_prefs == {}


def test_a_token_signed_for_something_else_is_rejected(make_member):
    m = make_member("student")
    foreign = signing.dumps({"m": m.pk, "t": "intros"}, salt="some.other.feature")  # right shape, wrong purpose
    assert post(foreign).status_code == 400
    wrong_type = signing.dumps({"m": m.pk, "t": "everything"}, salt=unsubscribe.SALT)
    assert post(wrong_type).status_code == 400
    not_a_member_id = signing.dumps({"m": "1; drop table", "t": "intros"}, salt=unsubscribe.SALT)
    assert post(not_a_member_id).status_code == 400


def test_an_expired_token_is_rejected(make_member, monkeypatch, settings):
    m = make_member("student")
    token = link_token(m)
    assert post(token).status_code == 200
    later = time.time() + settings.UNSUBSCRIBE_TOKEN_DAYS * 86400 + 60
    monkeypatch.setattr(signing.time, "time", lambda: later)
    r = post(token)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_token"


def test_a_token_for_a_deleted_member_does_nothing(make_member):
    m = make_member("student", deleted_at=timezone.now())
    assert post(link_token(m)).status_code == 400
    m2 = make_member("student", deletion_requested_at=timezone.now())
    assert post(link_token(m2)).status_code == 400


def test_the_token_carries_only_a_member_id_and_a_type(make_member):
    token = link_token(make_member("student", email="private@example.org", display_name="Private Person"))
    payload = signing.loads(token, salt=unsubscribe.SALT)
    assert set(payload) == {"m", "t"} and "private" not in token.lower()


def test_unsubscribing_is_rate_limited_per_address(make_member, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "unsubscribe_ip": (2, 60)}
    m = make_member("student")
    assert [post(link_token(m)).status_code for _ in range(3)] == [200, 200, 429]


def test_someone_elses_signed_in_session_does_not_matter(make_member, client_for):
    a, b = make_member("student"), make_member("student")
    r = client_for(b).post(f"/api/unsubscribe?token={link_token(a)}")  # b is signed in, but the link is a's
    assert r.status_code == 200
    a.refresh_from_db()
    b.refresh_from_db()
    assert prefs.resolved(a)["intros"]["email"] is False and prefs.resolved(b)["intros"]["email"] is True
