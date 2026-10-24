"""Under-18 rules (CLAUDE.md privacy, DESIGN.md §8): organisation-only posting, no contact from strangers, no drop."""

import pytest

from apps.messaging.models import Conversation
from apps.social.drop import build_all
from apps.social.models import DailyDrop

pytestmark = pytest.mark.django_db


@pytest.fixture
def cast(make_member, make_org):
    org, other = make_org("KIT"), make_org("Other College")
    return {
        "minor": make_member("student", org=org, is_minor=True, display_name="Minor"),
        "mate": make_member("student", org=org, display_name="Org mate"),
        "staff": make_member("partner_admin", org=org, display_name="KIT staff"),
        "stranger": make_member("founder", display_name="Stranger"),
        "friend": make_member("mentor", display_name="Friend"),
        "other_staff": make_member("partner_admin", org=other, display_name="Other staff"),
        "other_student": make_member("student", org=other, display_name="Other student"),
    }


def post_body(visibility, **kw):
    return {"body": "Built a line-following robot", "visibility": visibility, **kw}


# -- posting ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("visibility", ["everyone", "connections"])
def test_minor_cannot_post_publicly_or_to_connections(cast, client_for, visibility):
    r = client_for(cast["minor"]).post("/api/posts", post_body(visibility))
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_minor_can_post_to_their_organisation_only(cast, client_for):
    r = client_for(cast["minor"]).post("/api/posts", post_body("organisation"))
    assert r.status_code == 201 and r.json()["visibility"] == "organisation"


def test_minor_without_an_organisation_cannot_post_at_all(make_member, client_for):
    lone = make_member("student", is_minor=True)
    c = client_for(lone)
    assert c.post("/api/posts", post_body("organisation")).status_code == 403
    assert c.post("/api/posts", post_body("everyone")).status_code == 403


def test_a_minors_post_reaches_only_their_organisation(cast, client_for, connect):
    connect(cast["minor"], cast["friend"])  # even a connection outside the org does not see an org-only post
    post_id = client_for(cast["minor"]).post("/api/posts", post_body("organisation")).json()["id"]
    assert client_for(cast["mate"]).get(f"/api/posts/{post_id}").status_code == 200
    assert client_for(cast["friend"]).get(f"/api/posts/{post_id}").status_code == 404
    assert client_for(cast["stranger"]).get(f"/api/posts/{post_id}").status_code == 404
    assert client_for(cast["other_student"]).get(f"/api/posts/{post_id}").status_code == 404


def test_a_minors_profile_posts_are_a_404_for_strangers_and_visible_to_the_org(cast, client_for):
    client_for(cast["minor"]).post("/api/posts", post_body("organisation"))
    ghost = client_for(cast["stranger"]).get("/api/members/999999/posts")
    real = client_for(cast["stranger"]).get(f"/api/members/{cast['minor'].pk}/posts")
    assert real.status_code == 404 and real.json() == ghost.json()  # cannot tell a minor from a missing member
    assert len(client_for(cast["mate"]).get(f"/api/members/{cast['minor'].pk}/posts").json()) == 1


def test_a_minors_post_does_not_show_in_a_strangers_pulse(cast, client_for, connect):
    connect(cast["minor"], cast["stranger"])  # a connection who is outside the organisation
    client_for(cast["minor"]).post("/api/posts", post_body("organisation"))
    for who in ("stranger", "other_student"):
        assert client_for(cast[who]).get("/api/pulse").json()["items"] == []
    assert len(client_for(cast["mate"]).get("/api/pulse").json()["items"]) == 1


# -- messages ----------------------------------------------------------------------------------------
def start(client, member, text="Hi"):
    return client.post("/api/conversations", {"member_id": member.pk, "body": text})


def test_a_stranger_cannot_message_a_minor_and_gets_the_same_answer_as_for_nobody(cast, client_for):
    c = client_for(cast["stranger"])
    real, ghost = (
        c.post("/api/conversations", {"member_id": cast["minor"].pk, "body": "hey"}),
        c.post("/api/conversations", {"member_id": 999999, "body": "hey"}),
    )
    assert real.status_code == ghost.status_code == 404 and real.json() == ghost.json()
    assert not Conversation.objects.exists()


def test_an_org_mate_who_is_not_a_connection_cannot_message_a_minor(cast, client_for):
    assert start(client_for(cast["mate"]), cast["minor"]).status_code == 404


def test_a_minor_cannot_message_strangers_or_other_organisations(cast, client_for):
    c = client_for(cast["minor"])
    for who in ("stranger", "mate", "other_student", "other_staff"):
        assert start(c, cast[who]).status_code == 404, who
    assert not Conversation.objects.exists()


def test_a_minor_can_message_a_connection_directly(cast, client_for, connect):
    connect(cast["minor"], cast["friend"])
    r = start(client_for(cast["minor"]), cast["friend"])
    assert r.status_code == 201 and r.json()["conversation"]["status"] == "active"


def test_organisation_staff_can_reach_a_minor_as_a_request_and_the_minor_can_answer(cast, client_for):
    r = start(client_for(cast["staff"]), cast["minor"], "Hello from the placement cell")
    assert r.status_code == 201 and r.json()["conversation"]["status"] == "request"
    conv = r.json()["conversation"]["id"]
    inbox = client_for(cast["minor"]).get("/api/conversations?folder=requests").json()
    assert [c["id"] for c in inbox] == [conv]
    assert client_for(cast["minor"]).post(f"/api/conversations/{conv}/accept").json()["status"] == "active"
    assert client_for(cast["minor"]).post(f"/api/conversations/{conv}/messages", {"body": "Thanks"}).status_code == 201


def test_other_organisations_staff_cannot_reach_a_minor(cast, client_for):
    assert start(client_for(cast["other_staff"]), cast["minor"]).status_code == 404


def test_minor_can_message_their_own_staff_but_not_other_staff(cast, client_for):
    c = client_for(cast["minor"])
    assert start(c, cast["staff"]).status_code == 201
    assert start(c, cast["other_staff"]).status_code == 404


def test_the_rule_is_checked_on_every_send_not_just_the_first(cast, client_for, connect):
    link = connect(cast["minor"], cast["friend"])
    conv = start(client_for(cast["friend"]), cast["minor"]).json()["conversation"]["id"]
    link.delete()  # the connection ends
    assert client_for(cast["friend"]).post(f"/api/conversations/{conv}/messages", {"body": "still there?"}).status_code == 404
    assert client_for(cast["minor"]).post(f"/api/conversations/{conv}/messages", {"body": "hello"}).status_code == 404


def test_a_minor_has_no_requests_from_strangers_in_their_inbox(cast, client_for):
    start(client_for(cast["stranger"]), cast["minor"])
    start(client_for(cast["mate"]), cast["minor"])
    assert client_for(cast["minor"]).get("/api/conversations?folder=requests").json() == []


# -- connection requests ----------------------------------------------------------------------------
def ask(client, member):
    return client.post("/api/connections/requests", {"member_id": member.pk, "note": "Hi"})


def test_connection_requests_to_or_from_a_minor_stay_inside_one_organisation(cast, client_for):
    assert ask(client_for(cast["stranger"]), cast["minor"]).status_code == 404
    assert ask(client_for(cast["other_student"]), cast["minor"]).status_code == 404
    assert ask(client_for(cast["minor"]), cast["stranger"]).status_code == 404
    assert ask(client_for(cast["minor"]), cast["other_student"]).status_code == 404
    assert ask(client_for(cast["mate"]), cast["minor"]).status_code == 201


# -- discovery ----------------------------------------------------------------------------------------
def test_minors_get_no_daily_drop_and_are_never_dropped_to_others(cast, client_for, settings):
    from apps.matching.models import MatchResult

    MatchResult.objects.create(member=cast["stranger"], candidate=cast["minor"], score=0.9, reason="fit")
    MatchResult.objects.create(member=cast["minor"], candidate=cast["mate"], score=0.9, reason="fit")
    build_all()
    assert not DailyDrop.objects.filter(member=cast["minor"]).exists()
    assert not DailyDrop.objects.filter(member=cast["stranger"]).exists()
    assert client_for(cast["minor"]).get("/api/drop/today").json()["cards"] == []
