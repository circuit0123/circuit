"""B7 part 1: profile photos. Upload with purpose "avatar", then PUT /api/me/photo; `photo` appears wherever a person does."""

import pytest

from apps.accounts import deletion
from apps.events.models import Event
from apps.social.models import MediaUpload
from core.storage import get_storage

pytestmark = pytest.mark.django_db


def upload_avatar(client, data: bytes, purpose="avatar"):
    r = client.post("/api/media/uploads", {"purpose": purpose, "content_type": "image/png", "size": len(data)})
    assert r.status_code == 201, r.content
    up = MediaUpload.objects.get(pk=r.json()["id"])
    get_storage().put("avatars", f"{up.path}/original", data, "image/png")
    assert client.post(f"/api/media/uploads/{up.pk}/complete").status_code == 200
    return up


def test_an_avatar_is_stored_in_one_small_size(make_member, client_for, make_image):
    c = client_for(make_member())
    up = upload_avatar(c, make_image("PNG", (2000, 1000)))
    files = get_storage().files
    assert ("avatars", f"{up.path}/w480.webp") in files and ("avatars", f"{up.path}/w1440.webp") not in files
    assert ("avatars", f"{up.path}/original") not in files


def test_setting_a_photo_shows_it_on_me_and_to_other_people(make_member, client_for, connect, make_image):
    a, b = make_member(display_name="Asha"), make_member(display_name="Bala")
    connect(a, b)
    ca = client_for(a)
    up = upload_avatar(ca, make_image("PNG", (600, 600)))
    r = ca.put("/api/me/photo", {"upload_id": up.pk})
    assert r.status_code == 200 and r.json()["photo"].startswith("http")
    assert Event.objects.filter(type="member.photo_set", actor=a).exists()
    seen = client_for(b).get("/api/connections").json()
    assert next(p for p in seen if p["id"] == a.pk)["photo"].startswith("http")


def test_a_member_with_no_photo_has_null(make_member, client_for, connect):
    a, b = make_member(), make_member()
    connect(a, b)
    assert client_for(b).get("/api/connections").json()[0]["photo"] is None
    assert client_for(a).get("/api/me").json()["photo"] is None


def test_replacing_a_photo_deletes_the_old_files(make_member, client_for, make_image):
    m = make_member()
    c = client_for(m)
    first = upload_avatar(c, make_image("PNG", (600, 600)))
    c.put("/api/me/photo", {"upload_id": first.pk})
    second = upload_avatar(c, make_image("PNG", (600, 600)))
    c.put("/api/me/photo", {"upload_id": second.pk})
    assert ("avatars", f"{first.path}/w480.webp") not in get_storage().files
    assert not MediaUpload.objects.filter(pk=first.pk).exists()
    m.refresh_from_db()
    assert m.photo_path == second.path


def test_removing_the_photo_is_safe_to_repeat(make_member, client_for, make_image):
    m = make_member()
    c = client_for(m)
    up = upload_avatar(c, make_image("PNG", (600, 600)))
    c.put("/api/me/photo", {"upload_id": up.pk})
    assert c.delete("/api/me/photo").json()["photo"] is None
    assert c.delete("/api/me/photo").status_code == 200
    assert ("avatars", f"{up.path}/w480.webp") not in get_storage().files


def test_someone_elses_upload_is_a_404(make_member, client_for, make_image):
    a, b = make_member(), make_member()
    up = upload_avatar(client_for(a), make_image("PNG", (600, 600)))
    assert client_for(b).put("/api/me/photo", {"upload_id": up.pk}).status_code == 404


def test_a_post_image_cannot_be_used_as_a_photo(make_member, client_for, make_image):
    m = make_member()
    c = client_for(m)
    r = c.post("/api/media/uploads", {"purpose": "post", "content_type": "image/png", "size": 100})
    assert c.put("/api/me/photo", {"upload_id": r.json()["id"]}).status_code == 404


def test_an_unfinished_upload_is_refused(make_member, client_for):
    c = client_for(make_member())
    r = c.post("/api/media/uploads", {"purpose": "avatar", "content_type": "image/png", "size": 100})
    assert c.put("/api/me/photo", {"upload_id": r.json()["id"]}).status_code == 404


def test_a_student_cannot_upload_a_startup_logo(make_member, client_for):
    r = client_for(make_member("student")).post(
        "/api/media/uploads", {"purpose": "startup_logo", "content_type": "image/png", "size": 100}
    )
    assert r.status_code == 403


def test_an_under_18_photo_is_shown_to_nobody_else(make_member, client_for, connect, make_image):
    kid, friend = make_member("student", is_minor=True), make_member("student")
    connect(kid, friend)
    ck = client_for(kid)
    up = upload_avatar(ck, make_image("PNG", (600, 600)))
    mine = ck.put("/api/me/photo", {"upload_id": up.pk}).json()
    assert mine["photo"].startswith("http")  # they see their own
    assert client_for(friend).get("/api/connections").json()[0]["photo"] is None
    assert str(up.path) not in client_for(friend).get("/api/connections").content.decode()


def test_deleting_the_account_removes_the_photo(make_member, client_for, make_image):
    m = make_member()
    c = client_for(m)
    up = upload_avatar(c, make_image("PNG", (600, 600)))
    c.put("/api/me/photo", {"upload_id": up.pk})
    deletion._delete_files(m)
    assert ("avatars", f"{up.path}/w480.webp") not in get_storage().files


def test_the_photo_endpoints_reject_extra_fields(make_member, client_for):
    assert client_for(make_member()).put("/api/me/photo", {"upload_id": 1, "x": 1}).status_code == 422
