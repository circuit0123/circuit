"""B7 part 3: what the F6 screens still needed. Highlights, circuits we share, the headline, paging of build logs, push settings."""

import pytest

from apps.accounts import deletion
from apps.accounts.models import Member
from apps.events.models import Event
from apps.social.models import Highlight, MediaUpload, Post
from core.storage import get_storage
from tests.api.test_b7_profile import closed_circuit, picture_post

pytestmark = pytest.mark.django_db


def upload(client, data: bytes, purpose="highlight"):
    r = client.post("/api/media/uploads", {"purpose": purpose, "content_type": "image/png", "size": len(data)})
    assert r.status_code == 201, r.content
    up = MediaUpload.objects.get(pk=r.json()["id"])
    get_storage().put("posts", f"{up.path}/original", data, "image/png")
    assert client.post(f"/api/media/uploads/{up.pk}/complete").status_code == 200
    return up


def item(up, title="Voice assistant", **kw):
    return {"upload_id": up.pk, "title": title, "alt_text": "A phone showing the app", **kw}


# -- highlights -------------------------------------------------------------------------------------------
def test_pinned_highlights_show_on_the_profile_in_order(make_member, client_for, connect, make_image):
    a, b = make_member(display_name="Asha"), make_member()
    connect(a, b)
    ca = client_for(a)
    one, two = upload(ca, make_image("PNG", (600, 600))), upload(ca, make_image("PNG", (600, 600)))
    r = ca.put("/api/me/highlights", {"items": [item(two, "Second"), item(one, "First", link="https://example.com/x")]})
    assert r.status_code == 200 and [h["title"] for h in r.json()] == ["Second", "First"]
    assert Event.objects.filter(type="member.highlights_set", actor=a).exists()
    seen = client_for(b).get(f"/api/members/{a.pk}").json()["highlights"]
    assert [h["title"] for h in seen] == ["Second", "First"] and seen[1]["link"] == "https://example.com/x"
    assert seen[0]["image"]["w480"].startswith("http") and seen[0]["image"]["alt_text"] == "A phone showing the app"


def test_sending_the_list_again_keeps_pinned_pictures_and_drops_the_rest(make_member, client_for, make_image):
    m = make_member()
    c = client_for(m)
    keep, drop = upload(c, make_image("PNG", (600, 600))), upload(c, make_image("PNG", (600, 600)))
    c.put("/api/me/highlights", {"items": [item(keep), item(drop)]})
    assert c.put("/api/me/highlights", {"items": [item(keep, "Renamed")]}).json()[0]["title"] == "Renamed"
    assert MediaUpload.objects.filter(pk=keep.pk).exists() and not MediaUpload.objects.filter(pk=drop.pk).exists()
    assert ("posts", f"{drop.path}/w480.webp") not in get_storage().files
    assert c.put("/api/me/highlights", {"items": []}).json() == []
    assert not Highlight.objects.filter(member=m).exists()


def test_someone_elses_upload_or_the_wrong_kind_is_a_404(make_member, client_for, make_image):
    a, b = make_member(), make_member()
    ca, cb = client_for(a), client_for(b)
    theirs = upload(cb, make_image("PNG", (600, 600)))
    assert ca.put("/api/me/highlights", {"items": [item(theirs)]}).status_code == 404  # IDOR
    cb.put("/api/me/highlights", {"items": [item(theirs)]})
    assert ca.put("/api/me/highlights", {"items": [item(theirs)]}).status_code == 404  # pinned by b
    mine = client_for(a).post("/api/media/uploads", {"purpose": "avatar", "content_type": "image/png", "size": 10})
    assert ca.put("/api/me/highlights", {"items": [{**item(theirs), "upload_id": mine.json()["id"]}]}).status_code == 404
    assert Highlight.objects.filter(member=b).count() == 1 and not Highlight.objects.filter(member=a).exists()


@pytest.mark.parametrize(
    "bad",
    [{"title": ""}, {"title": "   "}, {"alt_text": ""}, {"link": "javascript:alert(1)"}, {"title": "x" * 81}, {"extra": 1}],
)
def test_a_bad_highlight_is_a_422(make_member, client_for, make_image, bad):
    c = client_for(make_member())
    up = upload(c, make_image("PNG", (600, 600)))
    assert c.put("/api/me/highlights", {"items": [{**item(up), **bad}]}).status_code == 422


def test_more_than_six_or_the_same_picture_twice_is_a_422(make_member, client_for, make_image):
    c = client_for(make_member())
    ups = [upload(c, make_image("PNG", (300, 300))) for _ in range(7)]
    assert c.put("/api/me/highlights", {"items": [item(u) for u in ups]}).status_code == 422
    assert c.put("/api/me/highlights", {"items": [item(ups[0]), item(ups[0])]}).status_code == 422
    assert c.put("/api/me/highlights", {"items": [item(u) for u in ups[:6]]}).status_code == 200


def test_an_under_18_members_highlights_are_for_them_alone(make_member, client_for, connect, make_image):
    kid, friend = make_member(is_minor=True), make_member()
    connect(kid, friend)
    ck = client_for(kid)
    assert ck.put("/api/me/highlights", {"items": [item(upload(ck, make_image("PNG", (300, 300))))]}).status_code == 200
    assert len(client_for(kid).get(f"/api/members/{kid.pk}").json()["highlights"]) == 1
    # an under-18 profile is a 404 to everyone else, so the highlights cannot be reached by any other route either
    assert client_for(friend).get(f"/api/members/{kid.pk}").status_code == 404
    from apps.accounts import highlights

    assert highlights.rows_for(friend, kid) == []  # and the serializer itself hides them


def test_highlights_of_a_hidden_member_are_a_404_to_strangers(make_member, client_for, make_image):
    hidden = make_member(profile_visibility="hidden")
    c = client_for(hidden)
    c.put("/api/me/highlights", {"items": [item(upload(c, make_image("PNG", (300, 300))))]})
    assert client_for(make_member()).get(f"/api/members/{hidden.pk}").status_code == 404


def test_deleting_an_account_removes_the_highlights(make_member, client_for, make_image):
    m = make_member()
    c = client_for(m)
    c.put("/api/me/highlights", {"items": [item(upload(c, make_image("PNG", (300, 300))))]})
    deletion.erase(m)
    assert not Highlight.objects.filter(member_id=m.pk).exists()


def test_signed_out_cannot_set_highlights(client_for):
    assert client_for(None).put("/api/me/highlights", {"items": []}).status_code == 401


# -- circuits we share ------------------------------------------------------------------------------------
def test_the_profile_lists_circuits_we_are_both_in(lists, make_member, client_for, connect):
    a, b, c, d = (make_member("student", level=2) for _ in range(4))
    connect(a, b)
    shared = closed_circuit(a, b, c)
    closed_circuit(b, c, d)  # a is not in this one
    body = client_for(a).get(f"/api/members/{b.pk}").json()
    assert [x["id"] for x in body["circuits_together"]] == [shared.pk]
    assert body["circuits_together"][0]["completed"] is True and len(body["circuits_together"][0]["month"]) == 7
    assert client_for(a).get(f"/api/members/{a.pk}").json()["circuits_together"] is None  # my own list is /api/circuits


def test_a_circuit_that_was_only_proposed_or_declined_is_never_shown(lists, make_member, client_for, connect):
    from apps.circuits.models import Circuit

    a, b, c = (make_member("student", level=2) for _ in range(3))
    connect(a, b)
    for status in ("proposed", "declined", "expired"):
        Circuit.objects.filter(pk=closed_circuit(a, b, c).pk).update(status=status)
    assert client_for(a).get(f"/api/members/{b.pk}").json()["circuits_together"] == []


def test_a_stranger_sees_no_shared_circuits_and_no_count(lists, make_member, client_for):
    a, b, c = (make_member("student", level=2) for _ in range(3))
    closed_circuit(b, c, make_member("student", level=2))
    body = client_for(a).get(f"/api/members/{b.pk}").json()
    assert body["circuits_together"] == [] and body["circuits_closed"] is None


# -- headline ---------------------------------------------------------------------------------------------
def test_headline_is_saved_and_used_everywhere_a_person_has_one(make_member, client_for, connect):
    a, b = make_member(bio="First line of the bio"), make_member()
    connect(a, b)
    ca = client_for(a)
    assert ca.get("/api/me").json()["headline"] == "First line of the bio"  # no headline yet: the start of the bio
    r = ca.patch("/api/me", {"headline": "  Frontend developer  "})
    assert r.status_code == 200 and r.json()["headline"] == "Frontend developer"
    assert client_for(b).get(f"/api/members/{a.pk}").json()["headline"] == "Frontend developer"
    assert ca.patch("/api/me", {"headline": ""}).json()["headline"] == "First line of the bio"


@pytest.mark.parametrize("bad", ["x" * 141, "two\nlines", None])
def test_a_bad_headline_is_a_422(make_member, client_for, bad):
    m = make_member(bio="bio")
    assert client_for(m).patch("/api/me", {"headline": bad}).status_code == 422
    m.refresh_from_db()
    assert m.headline == ""


def test_me_names_my_own_organisation(make_member, make_org, client_for):
    org = make_org("IIT Madras")
    assert client_for(make_member(org=org)).get("/api/me").json()["organisation_name"] == "IIT Madras"
    assert client_for(make_member()).get("/api/me").json()["organisation_name"] is None


# -- paging of a member's build logs ----------------------------------------------------------------------
def test_build_logs_come_in_pages_newest_first(make_member, client_for):
    a, viewer = make_member(), make_member()
    posts = [picture_post(a) for _ in range(5)]
    c = client_for(viewer)
    first = c.get(f"/api/members/{a.pk}/posts?limit=2").json()
    assert [p["id"] for p in first["items"]] == [posts[4].pk, posts[3].pk] and first["next_cursor"]
    second = c.get(f"/api/members/{a.pk}/posts?limit=2&cursor={first['next_cursor']}").json()
    assert [p["id"] for p in second["items"]] == [posts[2].pk, posts[1].pk]
    last = c.get(f"/api/members/{a.pk}/posts?limit=2&cursor={second['next_cursor']}").json()
    assert [p["id"] for p in last["items"]] == [posts[0].pk] and last["next_cursor"] is None
    assert "count" not in last


def test_a_bad_cursor_is_a_422_and_a_hidden_member_still_a_404(make_member, client_for):
    a = make_member()
    picture_post(a)
    c = client_for(make_member())
    for bad in ("nonsense", "W1sxXQ"):  # not base64 json, and a cursor of the wrong shape
        r = c.get(f"/api/members/{a.pk}/posts?cursor={bad}")
        assert r.status_code == 422 and r.json()["error"]["code"] == "bad_cursor"
    hidden = make_member(profile_visibility="hidden")
    assert c.get(f"/api/members/{hidden.pk}/posts").status_code == 404


def test_paging_only_ever_shows_posts_the_viewer_may_see(make_member, client_for):
    a = make_member()
    picture_post(a, "everyone")
    Post.objects.create(author=a, body="mine only", visibility="connections")
    items = client_for(make_member()).get(f"/api/members/{a.pk}/posts").json()["items"]
    assert [p["visibility"] for p in items] == ["everyone"]


# -- push settings ----------------------------------------------------------------------------------------
def test_push_quiet_hours_and_cap_have_defaults_and_can_change(make_member, client_for):
    c = client_for(make_member())
    n = c.get("/api/me/settings").json()["notifications"]
    assert n["intros"] == {"in_app": True, "email": True, "push": True} and n["announcements"]["push"] is False
    assert n["quiet_hours"] == {"start": 22, "end": 8} and n["push_daily_cap"] == 3 and n["quiet_hours_locked"] is False
    r = c.patch(
        "/api/me/notification-preferences",
        {"messages": {"push": False}, "quiet_hours": {"start": 23, "end": 7}, "push_daily_cap": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["messages"]["push"] is False and body["quiet_hours"] == {"start": 23, "end": 7} and body["push_daily_cap"] == 5
    assert c.patch("/api/me/notification-preferences", {"intros": {"email": False}}).json()["quiet_hours"]["start"] == 23  # kept
    assert c.get("/api/me/settings").json()["notifications"]["push_daily_cap"] == 5


@pytest.mark.parametrize(
    "bad",
    [
        {"push_daily_cap": 0},
        {"push_daily_cap": 11},
        {"quiet_hours": {"start": 24, "end": 7}},
        {"quiet_hours": {"start": 7, "end": 7}},
        {"intros": {"sms": True}},
    ],
)
def test_bad_push_settings_are_a_422(make_member, client_for, bad):
    assert client_for(make_member()).patch("/api/me/notification-preferences", bad).status_code == 422


def test_an_under_18_member_cannot_change_quiet_hours_or_raise_the_cap(make_member, client_for):
    kid = make_member(is_minor=True)
    c = client_for(kid)
    n = c.get("/api/me/settings").json()["notifications"]
    assert n["quiet_hours_locked"] is True and n["quiet_hours"] == {"start": 19, "end": 9}
    for bad in ({"quiet_hours": {"start": 23, "end": 7}}, {"push_daily_cap": 5}):
        r = c.patch("/api/me/notification-preferences", bad)
        assert r.status_code == 403 and r.json()["error"]["code"] == "under_18_restricted"
    assert c.patch("/api/me/notification-preferences", {"push_daily_cap": 1}).json()["push_daily_cap"] == 1  # fewer is fine
    assert Member.objects.get(pk=kid.pk).notification_prefs["delivery"]["push_daily_cap"] == 1


def test_every_event_the_highlights_code_records_is_a_known_event_type():
    """The 500 on PUT /api/me/highlights was `record()` refusing an event name nobody had registered."""
    from apps.events.services import EVENT_TYPES

    assert "member.highlights_set" in EVENT_TYPES
