import io
import json

import pytest
from PIL import Image

from apps.events.models import Event
from apps.notifications.models import Notification
from apps.social.models import MediaUpload, Post
from core.storage import get_storage

pytestmark = pytest.mark.django_db


def upload_image(client, member, data: bytes, content_type="image/png", purpose="post"):
    """The browser's flow: ask for a signed URL, PUT the bytes (here: straight into the fake storage), then complete."""
    r = client.post("/api/media/uploads", {"purpose": purpose, "content_type": content_type, "size": len(data)})
    assert r.status_code == 201, r.content
    up = MediaUpload.objects.get(pk=r.json()["id"])
    get_storage().put("posts" if purpose == "post" else "messages", f"{up.path}/original", data, content_type)
    return up, client.post(f"/api/media/uploads/{up.pk}/complete")


# -- media ----------------------------------------------------------------------------------------------
def test_upload_flow_stores_two_reencoded_sizes_and_deletes_the_original(make_member, client_for, make_image):
    me = make_member()
    up, r = upload_image(client_for(me), me, make_image("PNG", (2000, 1000)))
    assert r.status_code == 200 and r.json()["status"] == "ready" and (r.json()["width"], r.json()["height"]) == (2000, 1000)
    store = get_storage()
    assert ("posts", f"{up.path}/original") not in store.files
    big = Image.open(io.BytesIO(store.files[("posts", f"{up.path}/w1440.webp")]))
    small = Image.open(io.BytesIO(store.files[("posts", f"{up.path}/w480.webp")]))
    assert big.format == "WEBP" and big.width == 1440 and small.width == 480
    assert Event.objects.filter(type="media.uploaded").count() == 1


def test_gps_and_camera_metadata_do_not_survive(make_member, client_for, make_image):
    me = make_member()
    original = make_image("JPEG", exif=True)
    assert Image.open(io.BytesIO(original)).getexif().get(0x010F) == "TestCam"
    up, r = upload_image(client_for(me), me, original, "image/jpeg")
    assert r.status_code == 200
    for name in ("w1440.webp", "w480.webp"):
        out = Image.open(io.BytesIO(get_storage().files[("posts", f"{up.path}/{name}")]))
        assert not out.getexif() and b"TestCam" not in get_storage().files[("posts", f"{up.path}/{name}")]


def test_small_images_are_not_enlarged(make_member, client_for, make_image):
    me = make_member()
    up, _ = upload_image(client_for(me), me, make_image("PNG", (300, 200)))
    img = Image.open(io.BytesIO(get_storage().files[("posts", f"{up.path}/w1440.webp")]))
    assert img.width == 300


def test_a_file_that_is_not_an_image_is_refused_and_deleted(make_member, client_for):
    me = make_member()
    up, r = upload_image(client_for(me), me, b"<html>not an image</html>")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_image"
    assert ("posts", f"{up.path}/original") not in get_storage().files
    up.refresh_from_db()
    assert up.status == "pending"


def test_a_real_image_in_a_disallowed_format_is_refused(make_member, client_for, make_image):
    me = make_member()
    _, r = upload_image(client_for(me), me, make_image("GIF"), "image/png")  # lies about the type
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_image"


def test_completing_before_uploading_is_a_409_and_repeating_is_safe(make_member, client_for, make_image):
    me = make_member()
    c = client_for(me)
    r = c.post("/api/media/uploads", {"purpose": "post", "content_type": "image/png", "size": 10})
    uid = r.json()["id"]
    assert c.post(f"/api/media/uploads/{uid}/complete").status_code == 409
    up, first = upload_image(c, me, make_image())
    assert first.status_code == 200 and c.post(f"/api/media/uploads/{up.pk}/complete").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"purpose": "post", "content_type": "image/gif", "size": 10},
        {"purpose": "post", "content_type": "image/png", "size": 0},
        {"purpose": "video", "content_type": "image/png", "size": 10},
    ],
)
def test_upload_request_validation(make_member, client_for, body):
    assert client_for(make_member()).post("/api/media/uploads", body).status_code == 422


def test_upload_over_5mb_is_refused_up_front(make_member, client_for):
    r = client_for(make_member()).post(
        "/api/media/uploads", {"purpose": "post", "content_type": "image/png", "size": 5 * 1024 * 1024 + 1}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "image_too_large"


def test_upload_rate_limit(make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "upload": (2, 60)}
    c = client_for(make_member())
    codes = [
        c.post("/api/media/uploads", {"purpose": "post", "content_type": "image/png", "size": 10}).status_code for _ in range(3)
    ]
    assert codes == [201, 201, 429]


# -- creating posts -----------------------------------------------------------------------------------
def test_create_a_build_log_with_images_tags_and_a_link(make_member, make_org, client_for, make_image, lists):
    me = make_member("student", org=make_org(), display_name="Ravi")
    c = client_for(me)
    ups = [upload_image(c, me, make_image())[0] for _ in range(2)]
    r = c.post(
        "/api/posts",
        {
            "body": "Shipped the login screen",
            "link": "https://github.com/ravi/app",
            "visibility": "organisation",
            "capabilities": ["ui-design", "ux-design"],
            "media": [{"upload_id": u.pk, "alt_text": f"screen {i}"} for i, u in enumerate(ups)],
        },
    )
    assert r.status_code == 201, r.content
    post = r.json()
    assert [m["alt_text"] for m in post["media"]] == ["screen 0", "screen 1"]
    assert post["media"][0]["w1440"].startswith("https://storage.test/read/posts/") and post["author"]["display_name"] == "Ravi"
    assert len(post["capabilities"]) == 2 and post["my_reactions"] == []
    assert Event.objects.filter(type="post.created", target_id=post["id"]).exists()


@pytest.mark.parametrize(
    "extra, code",
    [
        ({"body": "  "}, "empty_post"),
        ({"body": "x" * 501}, None),
        ({"link": "javascript:alert(1)"}, None),
        ({"link": "ftp://example.com/x"}, None),
        ({"capabilities": ["a", "b", "c", "d"]}, None),
        ({"capabilities": ["not-a-capability"]}, "unknown_capability"),
        ({"visibility": "friends"}, None),
    ],
)
def test_post_validation(make_member, make_org, client_for, lists, extra, code):
    me = make_member("student", org=make_org())
    r = client_for(me).post("/api/posts", {"body": "hello", "visibility": "everyone", **extra})
    assert r.status_code == 422
    if code:
        assert r.json()["error"]["code"] == code


def test_more_than_four_images_or_missing_alt_text_is_refused(make_member, client_for, make_image):
    me = make_member()
    c = client_for(me)
    ups = [upload_image(c, me, make_image())[0] for _ in range(5)]
    five = [{"upload_id": u.pk, "alt_text": "x"} for u in ups]
    assert c.post("/api/posts", {"body": "", "visibility": "everyone", "media": five}).status_code == 422
    assert (
        c.post(
            "/api/posts", {"body": "", "visibility": "everyone", "media": [{"upload_id": ups[0].pk, "alt_text": ""}]}
        ).status_code
        == 422
    )
    assert not Post.objects.exists()


def test_organisation_visibility_needs_an_organisation(make_member, client_for):
    r = client_for(make_member("student")).post("/api/posts", {"body": "hi", "visibility": "organisation"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_organisation"


def test_post_rate_limit(make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "post": (2, 60)}
    c = client_for(make_member())
    codes = [c.post("/api/posts", {"body": "hi", "visibility": "everyone"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_deleting_a_post_removes_its_images(make_member, client_for, make_image):
    me = make_member()
    c = client_for(me)
    up, _ = upload_image(c, me, make_image())
    pid = c.post("/api/posts", {"body": "", "visibility": "everyone", "media": [{"upload_id": up.pk, "alt_text": "x"}]}).json()[
        "id"
    ]
    assert c.delete(f"/api/posts/{pid}").status_code == 204
    assert not [k for k in get_storage().files if up.path in k[1]]
    assert not MediaUpload.objects.filter(pk=up.pk).exists()
    assert Event.objects.filter(type="post.deleted", target_id=pid).exists()


# -- no public counts ----------------------------------------------------------------------------------
COUNT_WORDS = ("count", "total", "likes", "followers", "views")


def keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys(v)


def test_only_the_author_sees_reaction_totals(make_member, make_post, connect, client_for):
    author, fan, other = make_member("student"), make_member("founder"), make_member("mentor")
    post = make_post(author, "everyone")
    for who in (fan, other):
        assert client_for(who).put(f"/api/posts/{post.pk}/reactions/helpful").status_code == 204
    assert client_for(fan).put(f"/api/posts/{post.pk}/reactions/intro_me").status_code == 204
    client_for(fan).post(f"/api/posts/{post.pk}/replies", {"body": "Nice"})

    mine = client_for(author).get(f"/api/posts/{post.pk}").json()
    assert mine["private_stats"] == {"reactions": {"helpful": 2, "intro_me": 1}, "replies": 1}

    seen_by_fan = client_for(fan).get(f"/api/posts/{post.pk}").json()
    assert seen_by_fan["private_stats"] is None and seen_by_fan["my_reactions"] == ["helpful", "intro_me"]
    seen_by_other = client_for(other).get(f"/api/posts/{post.pk}").json()
    assert seen_by_other["my_reactions"] == ["helpful"]
    for payload in (seen_by_fan, seen_by_other, client_for(other).get(f"/api/members/{author.pk}/posts").json()):
        assert not [k for k in keys(payload) if any(w in k for w in COUNT_WORDS)], payload


def test_no_endpoint_exposes_follower_or_connection_counts(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    for path in ("/api/connections", f"/api/members/{a.pk}", "/api/me/follows", f"/api/members/{a.pk}/posts"):
        body = client_for(b).get(path).json()
        assert not [k for k in keys(body) if any(w in k for w in ("followers", "connection_count", "likes", "views"))], path


# -- reactions and replies ------------------------------------------------------------------------------
def test_reacting_is_safe_to_repeat_and_logged_once(make_member, make_post, client_for):
    author, fan = make_member("student"), make_member("founder")
    post = make_post(author, "everyone")
    c = client_for(fan)
    assert c.put(f"/api/posts/{post.pk}/reactions/lets_talk").status_code == 204
    assert c.put(f"/api/posts/{post.pk}/reactions/lets_talk").status_code == 204
    assert Event.objects.filter(type="reaction.added").count() == 1
    assert c.delete(f"/api/posts/{post.pk}/reactions/lets_talk").status_code == 204
    assert c.delete(f"/api/posts/{post.pk}/reactions/lets_talk").status_code == 204
    assert Event.objects.filter(type="reaction.removed").count() == 1
    assert c.put(f"/api/posts/{post.pk}/reactions/love").status_code == 422


def test_replies_nest_one_level_and_notify_the_author(make_member, make_post, client_for):
    author, fan, third = make_member("student"), make_member("founder"), make_member("mentor")
    post = make_post(author, "everyone")
    top = client_for(fan).post(f"/api/posts/{post.pk}/replies", {"body": "How did you do auth?"})
    assert top.status_code == 201
    child = client_for(author).post(f"/api/posts/{post.pk}/replies", {"body": "Supabase", "parent_id": top.json()["id"]})
    assert child.status_code == 201
    grandchild = client_for(third).post(f"/api/posts/{post.pk}/replies", {"body": "deep", "parent_id": child.json()["id"]})
    assert grandchild.status_code == 422 and grandchild.json()["error"]["code"] == "reply_too_deep"
    thread = client_for(third).get(f"/api/posts/{post.pk}/replies").json()
    assert len(thread) == 1 and [r["body"] for r in thread[0]["replies"]] == ["Supabase"]
    kinds = list(Notification.objects.filter(member=author).values_list("kind", "payload"))
    assert kinds == [("post.reply", {"post_id": post.pk, "reply_id": top.json()["id"]})]  # not for their own reply


@pytest.mark.parametrize("body", ["", "x" * 301])
def test_reply_length_limits(make_member, make_post, client_for, body):
    me = make_member()
    assert client_for(me).post(f"/api/posts/{make_post(me).pk}/replies", {"body": body}).status_code == 422


def test_replies_from_blocked_people_are_left_out(make_member, make_post, block, client_for):
    author, annoying, reader = make_member("student"), make_member("founder"), make_member("mentor")
    post = make_post(author, "everyone")
    client_for(annoying).post(f"/api/posts/{post.pk}/replies", {"body": "spam"})
    block(reader, annoying)
    assert client_for(reader).get(f"/api/posts/{post.pk}/replies").json() == []
    assert len(client_for(author).get(f"/api/posts/{post.pk}/replies").json()) == 1


def test_reply_rate_limit(make_member, make_post, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "reply": (1, 60)}
    me = make_member()
    post = make_post(me)
    codes = [client_for(me).post(f"/api/posts/{post.pk}/replies", {"body": "a"}).status_code for _ in range(2)]
    assert codes == [201, 429]


def test_blocked_posts_are_404_in_both_directions(make_member, make_post, block, client_for):
    a, b = make_member("student"), make_member("founder")
    post = make_post(a, "everyone")
    block(b, a)
    assert client_for(b).get(f"/api/posts/{post.pk}").status_code == 404
    assert client_for(b).get(f"/api/members/{a.pk}/posts").status_code == 404


def test_json_shape_of_error_for_unseen_post(make_member, make_post, client_for):
    a, b = make_member("student"), make_member("founder")
    r = client_for(b).get(f"/api/posts/{make_post(a, 'connections').pk}")
    assert r.status_code == 404 and set(json.loads(r.content)["error"]) == {"code", "message", "details"}
