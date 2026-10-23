from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.events.models import Event
from apps.social.drop import build_all, drop_day, next_drop_at
from apps.social.models import DailyDrop, Follow, Post, StoryView

pytestmark = pytest.mark.django_db


def age(post: Post, **delta) -> Post:
    Post.objects.filter(pk=post.pk).update(created_at=timezone.now() - timedelta(**delta))
    post.refresh_from_db()
    return post


@pytest.fixture
def me_and_friends(make_member, make_org, connect):
    org = make_org()
    me = make_member("student", org=org, display_name="Me")
    friend = make_member("founder", display_name="Friend")
    mate = make_member("student", org=org, display_name="Mate")
    stranger = make_member("mentor", display_name="Stranger")
    connect(me, friend)
    return me, friend, mate, stranger


# -- Pulse -------------------------------------------------------------------------------------------
def test_pulse_shows_connections_org_and_followed_teams_but_not_strangers_or_myself(
    me_and_friends, make_member, make_post, make_startup, client_for
):
    me, friend, mate, stranger = me_and_friends
    from apps.startups.models import StartupMember

    founder = make_member("founder", display_name="Team")
    startup = make_startup(claimed_by=founder)
    StartupMember.objects.create(startup=startup, member=founder)
    Follow.objects.create(member=me, startup=startup)
    for name, who in {"friend": friend, "mate": mate, "stranger": stranger, "me": me, "team": founder}.items():
        make_post(who, "everyone", body=name)
    items = client_for(me).get("/api/pulse").json()["items"]
    bodies = {i["post"]["body"] for i in items if i["kind"] == "post"}
    assert bodies == {"friend", "mate", "team"}


def test_pulse_is_newest_first_and_only_last_7_days(me_and_friends, make_post, client_for):
    me, friend, *_ = me_and_friends
    new, mid = make_post(friend, "everyone", body="new"), age(make_post(friend, "everyone", body="mid"), days=3)
    age(make_post(friend, "everyone", body="old"), days=8)
    items = client_for(me).get("/api/pulse").json()["items"]
    assert [i["post"]["body"] for i in items] == ["new", "mid"] and new.pk and mid.pk


def test_pulse_respects_post_visibility(me_and_friends, make_post, client_for):
    me, friend, mate, _ = me_and_friends
    make_post(friend, "organisation", body="friends org-only")  # friend has no org: nobody sees it
    make_post(mate, "connections", body="mate for connections")  # me is not connected to mate
    make_post(mate, "organisation", body="mate org")
    got = {i["post"]["body"] for i in client_for(me).get("/api/pulse").json()["items"]}
    assert got == {"mate org"}


def test_pulse_pages_with_a_cursor_and_ends_caught_up(me_and_friends, make_post, client_for):
    me, friend, *_ = me_and_friends
    for n in range(5):
        age(make_post(friend, "everyone", body=f"p{n}"), minutes=50 - n)
    c = client_for(me)
    first = c.get("/api/pulse?limit=2").json()
    assert [i["post"]["body"] for i in first["items"]] == ["p4", "p3"] and first["caught_up"] is False and first["next_cursor"]
    second = c.get(f"/api/pulse?limit=2&cursor={first['next_cursor']}").json()
    assert [i["post"]["body"] for i in second["items"]] == ["p2", "p1"]
    last = c.get(f"/api/pulse?limit=2&cursor={second['next_cursor']}").json()
    assert [i["post"]["body"] for i in last["items"]] == ["p0"] and last["caught_up"] is True and last["next_cursor"] is None


def test_a_bad_cursor_is_a_clean_422(me_and_friends, client_for):
    me, *_ = me_and_friends
    for cursor in ("garbage", "W10", "WzEsInBvc3QiLCJ4Il0"):  # not base64 json / empty list / wrong types
        r = client_for(me).get(f"/api/pulse?cursor={cursor}")
        assert r.status_code == 422 and r.json()["error"]["code"] == "bad_cursor", cursor


def test_after_marking_seen_pulse_only_shows_newer_items_and_include_seen_brings_the_rest_back(
    me_and_friends, make_post, client_for
):
    me, friend, *_ = me_and_friends
    age(make_post(friend, "everyone", body="before"), hours=2)
    c = client_for(me)
    assert c.post("/api/pulse/seen").status_code == 204
    after = c.get("/api/pulse").json()
    assert after["items"] == [] and after["caught_up"] is True
    make_post(friend, "everyone", body="after")
    assert [i["post"]["body"] for i in c.get("/api/pulse").json()["items"]] == ["after"]
    everything = c.get("/api/pulse?include_seen=true").json()["items"]
    assert [(i["post"]["body"], i["seen"]) for i in everything] == [("after", False), ("before", True)]
    assert Event.objects.filter(type="pulse.seen").count() == 1


def test_pulse_includes_nearby_matching_roles_for_students_and_a_skills_card(make_member, make_startup, lists, client_for):
    from apps.jobs.models import Job, JobCapability
    from apps.matching.models import Capability, MemberSkill

    student = make_member("student", city="Chennai", location=Point(80.27, 13.08, srid=4326))
    ui = Capability.objects.get(slug="ui-design")
    MemberSkill.objects.create(member=student, capability=ui, level=2)
    near, far = (
        make_startup("Near", "near.io", 13.09, 80.28, hiring=True),
        make_startup("Far", "far.io", 19.07, 72.87, hiring=True),
    )
    for s, title in ((near, "UI intern"), (far, "UI intern in Mumbai")):
        job = Job.objects.create(startup=s, title=title)
        JobCapability.objects.create(job=job, capability=ui)
    items = client_for(student).get("/api/pulse").json()["items"]
    roles = [i["role"]["title"] for i in items if i["kind"] == "role"]
    assert roles == ["UI intern"]
    card = [i for i in items if i["kind"] == "skills_in_demand"]
    assert len(card) == 1 and card[0]["skills_in_demand"]["skills"][0] == {"slug": "ui-design", "name": ui.name, "open_roles": 1}


def test_pulse_includes_a_circuit_closed_by_a_connection_but_not_by_strangers(me_and_friends, make_member, client_for):
    from apps.circuits.models import Circuit, CircuitLeg, CircuitRound
    from apps.events.services import record
    from apps.matching.models import Capability

    me, friend, mate, stranger = me_and_friends
    third = make_member("founder")
    cap = Capability.objects.create(slug="x", name="X", category="c")
    rnd = CircuitRound.objects.create(week="2026-W43")
    circuit = Circuit.objects.create(round=rnd, status="completed", score=0.5, consent_deadline=timezone.now())
    for g, r in ((friend, mate), (mate, third), (third, friend)):
        CircuitLeg.objects.create(circuit=circuit, giver=g, receiver=r, capability=cap)
    record("circuit.completed", target_type="circuit", target_id=circuit.pk)
    kinds = [i["activity"]["type"] for i in client_for(me).get("/api/pulse").json()["items"] if i["kind"] == "activity"]
    assert kinds == ["circuit_completed"]
    assert [i for i in client_for(stranger).get("/api/pulse").json()["items"] if i["kind"] == "activity"] == []


# -- Today strip -------------------------------------------------------------------------------------
def test_today_lists_people_who_posted_in_the_last_24_hours_unseen_first(me_and_friends, make_post, client_for):
    me, friend, mate, stranger = me_and_friends
    make_post(friend, "everyone", body="f")
    make_post(mate, "organisation", body="m")
    make_post(stranger, "everyone", body="s")
    age(make_post(friend, "everyone", body="stale"), hours=30)
    strip = client_for(me).get("/api/today").json()
    assert sorted(c["name"] for c in strip) == ["Friend", "Mate"] and all(not c["seen"] for c in strip)
    assert [p["body"] for c in strip if c["name"] == "Friend" for p in c["posts"]] == ["f"]


def test_viewing_a_circle_marks_it_seen_until_something_newer_arrives(me_and_friends, make_post, client_for):
    me, friend, *_ = me_and_friends
    make_post(friend, "everyone", body="one")
    c = client_for(me)
    assert c.post("/api/today/seen", {"kind": "member", "id": friend.pk}).status_code == 204
    assert c.post("/api/today/seen", {"kind": "member", "id": friend.pk}).status_code == 204  # repeat is fine
    assert StoryView.objects.filter(viewer=me).count() == 1
    assert c.get("/api/today").json()[0]["seen"] is True
    make_post(friend, "everyone", body="two")
    assert c.get("/api/today").json()[0]["seen"] is False


def test_today_includes_followed_startups_with_new_roles(make_member, make_startup, client_for):
    from apps.jobs.models import Job

    me = make_member("student")
    s = make_startup("Acme", "acme.io", hiring=True)
    Job.objects.create(startup=s, title="Intern")
    assert client_for(me).get("/api/today").json() == []
    Follow.objects.create(member=me, startup=s)
    strip = client_for(me).get("/api/today").json()
    assert [(c["kind"], c["name"], [r["title"] for r in c["roles"]]) for c in strip] == [("startup", "Acme", ["Intern"])]
    assert client_for(me).post("/api/today/seen", {"kind": "startup", "id": s.pk}).status_code == 204
    assert client_for(me).get("/api/today").json()[0]["seen"] is True


def test_today_leaves_out_blocked_people(me_and_friends, make_post, block, client_for):
    me, friend, *_ = me_and_friends
    make_post(friend, "everyone")
    block(me, friend)
    assert client_for(me).get("/api/today").json() == []


# -- Daily Drop --------------------------------------------------------------------------------------
@pytest.fixture
def matched(make_member):
    from apps.matching.models import MatchResult

    me = make_member("student", display_name="Me")
    others = [make_member("founder", display_name=f"Candidate {i}") for i in range(5)]
    for i, o in enumerate(others):
        MatchResult.objects.create(member=me, candidate=o, score=0.94 - i * 0.08, reason=f"reason {i}", is_bridge=i == 1)
    return me, others


def test_build_creates_three_per_member_and_is_idempotent(matched, client_for):
    me, others = matched
    first = build_all()
    assert first["built"] == 1
    drop = DailyDrop.objects.get(member=me)
    assert [c["member_id"] for c in drop.candidates] == [o.pk for o in others[:3]]
    assert build_all()["built"] == 0 and DailyDrop.objects.count() == 1
    out = client_for(me).get("/api/drop/today").json()
    assert [c["reason"] for c in out["cards"]] == ["reason 0", "reason 1", "reason 2"]
    assert [c["is_bridge"] for c in out["cards"]] == [False, True, False] and out["done"] is False


def test_drop_skips_connections_and_recently_dropped_people(matched, connect):
    me, others = matched
    connect(me, others[0])
    build_all()
    assert [c["member_id"] for c in DailyDrop.objects.get(member=me).candidates] == [o.pk for o in others[1:4]]
    tomorrow = timezone.now() + timedelta(days=1)
    build_all(tomorrow)
    second = DailyDrop.objects.filter(member=me).order_by("-date").first()
    assert [c["member_id"] for c in second.candidates] == [others[4].pk]  # the others were shown yesterday


def test_swiping_records_the_choice_and_finishes_the_drop(matched, client_for):
    me, others = matched
    build_all()
    c = client_for(me)
    for i, o in enumerate(others[:3]):
        r = c.post(f"/api/drop/today/{o.pk}/swipe", {"direction": "intro" if i == 0 else "skip"})
        assert r.status_code == 200
    out = r.json()
    assert [x["outcome"] for x in out["cards"]] == ["intro", "skip", "skip"] and out["done"] is True
    assert Event.objects.filter(type="drop.swiped", actor=me).count() == 3
    assert c.post(f"/api/drop/today/{others[0].pk}/swipe", {"direction": "intro"}).status_code == 200  # same answer: fine
    assert Event.objects.filter(type="drop.swiped").count() == 3
    assert c.post(f"/api/drop/today/{others[0].pk}/swipe", {"direction": "skip"}).status_code == 409
    assert c.post(f"/api/drop/today/{others[4].pk}/swipe", {"direction": "skip"}).status_code == 404  # not in today's drop


def test_a_blocked_or_hidden_candidate_disappears_from_the_drop(matched, block, client_for):
    me, others = matched
    build_all()
    block(me, others[0])
    others[1].profile_visibility = "hidden"
    others[1].save()
    assert [c["reason"] for c in client_for(me).get("/api/drop/today").json()["cards"]] == ["reason 2"]


def test_drop_day_starts_at_8am_ist():
    from datetime import UTC, datetime

    before, after = datetime(2026, 10, 23, 2, 0, tzinfo=UTC), datetime(2026, 10, 23, 3, 0, tzinfo=UTC)  # 07:30 and 08:30 IST
    assert drop_day(before).isoformat() == "2026-10-22" and drop_day(after).isoformat() == "2026-10-23"
    assert next_drop_at(after).isoformat() == "2026-10-24T08:00:00+05:30"


def test_the_command_runs(matched, capsys):
    from django.core.management import call_command

    call_command("build_daily_drops")
    assert "1 drops built" in capsys.readouterr().out


# -- Daily Drop: reason first, strength in words ------------------------------------------------------------
def test_drop_never_includes_a_match_below_good_and_labels_the_rest(make_member):
    from apps.matching.models import MatchResult

    me = make_member("student", display_name="Me")
    scores = {"strong": 0.8, "good": 0.6, "weak": 0.54}
    people = {k: make_member("founder", display_name=k) for k in scores}
    for k, o in people.items():
        MatchResult.objects.create(member=me, candidate=o, score=scores[k], reason=k, is_bridge=False)
    build_all()
    got = {c["member_id"]: c["strength"] for c in DailyDrop.objects.get(member=me).candidates}
    assert got == {people["strong"].pk: "strong", people["good"].pk: "good"}


def test_drop_cards_say_what_they_offer_who_connects_us_and_show_their_work(make_member, make_post, connect, client_for, lists):
    from apps.matching.models import Capability, MatchResult, Need, Offer
    from apps.social.models import MediaUpload, PostMedia

    me = make_member("student", display_name="Me")
    broker = make_member("mentor", display_name="Meera")
    sakthi = make_member("investor", display_name="Sakthi")
    connect(me, broker)
    connect(broker, sakthi)
    mentoring, seo = Capability.objects.get(slug="mentoring"), Capability.objects.get(slug="seo")
    Need.objects.create(member=me, capability=mentoring)
    Offer.objects.create(member=sakthi, capability=mentoring)
    Offer.objects.create(member=sakthi, capability=seo)  # I do not need this one
    MatchResult.objects.create(
        member=me, candidate=sakthi, score=0.7, reason="They offer mentoring, which you need.", is_bridge=False
    )
    post = make_post(sakthi, body="Our board")
    up = MediaUpload.objects.create(owner=sakthi, purpose="post", path="post/1/x", status="ready", width=10, height=10)
    PostMedia.objects.create(post=post, upload=up, alt_text="A board with three columns", order=0)
    build_all()
    [card] = client_for(me).get("/api/drop/today").json()["cards"]
    assert card["strength"] == "good" and card["help_with"] == "Mentoring" and card["offers_you_need"] == ["Mentoring"]
    assert card["via"]["id"] == broker.pk
    assert card["image"]["alt"] == "A board with three columns"
    assert "score" not in card and "score_percent" not in card


def test_matches_show_strength_in_words_and_no_number(make_member):
    from apps.matching.models import MatchResult

    me, other = make_member("student", display_name="Me"), make_member("founder", display_name="Other")
    MatchResult.objects.create(member=me, candidate=other, score=0.42, reason="r", is_bridge=False)
    from apps.matching.services import strength_for

    assert [strength_for(x) for x in (0.8, 0.75, 0.6, 0.55, 0.54, 0.1)] == ["strong", "strong", "good", "good", None, None]
