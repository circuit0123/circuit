"""Stage 7: data export (DPDP). Contains only the requesting member's own data; the link is signed, tied to them and expires."""

import io
import json
import time
import zipfile
from datetime import timedelta

import pytest
from django.core import mail, signing
from django.utils import timezone

from apps.accounts import export
from apps.accounts.models import ConnectionRequest, DataExport
from apps.events.models import Event
from apps.matching.models import Capability, Need, Offer
from apps.messaging.models import Conversation, Message
from apps.notifications.services import notify
from apps.social.models import MediaUpload, Reply
from core.storage import get_storage

pytestmark = pytest.mark.django_db
BUCKET = "private"


def ask(client):
    return client.post("/api/me/export")


def run_job():
    return export.build_pending()


def zip_of(row) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(get_storage().get(BUCKET, row.path)))


def data_of(row) -> dict:
    return json.loads(zip_of(row).read("data.json"))


@pytest.fixture
def two(make_member, connect, make_post):
    """Asha (the exporter) and Ravi, who wrote things to her and has secrets of his own."""
    cap = Capability.objects.order_by("id").first()
    asha = make_member(
        "founder", display_name="Asha Rao", email="asha@example.org", bio="Asha bio: building a farm app", city="Chennai"
    )
    ravi = make_member("mentor", display_name="Ravi Menon", email="ravi@example.org", bio="RAVI-SECRET-BIO", city="Pune")
    connect(asha, ravi)
    Need.objects.create(member=asha, capability=cap, description="asha needs help")
    Offer.objects.create(member=ravi, capability=cap, description="RAVI-SECRET-OFFER")
    asha_post, ravi_post = make_post(asha, "everyone", body="ASHA-POST"), make_post(ravi, "everyone", body="RAVI-SECRET-POST")
    Reply.objects.create(post=ravi_post, author=asha, body="ASHA-REPLY")
    Reply.objects.create(post=asha_post, author=ravi, body="RAVI-SECRET-REPLY")
    conv = Conversation.objects.create(
        member_a_id=min(asha.pk, ravi.pk), member_b_id=max(asha.pk, ravi.pk), started_by=ravi, status="active"
    )
    Message.objects.create(conversation=conv, sender=ravi, body="RAVI-SECRET-MESSAGE")
    Message.objects.create(conversation=conv, sender=asha, body="ASHA-MESSAGE")
    ConnectionRequest.objects.create(sender=ravi, recipient=asha, note="RAVI-SECRET-NOTE", status="accepted")
    notify(asha, "intro.received", actor=ravi, intro_id=1)
    up = MediaUpload.objects.create(
        owner=asha, purpose="post", path=f"post/{asha.pk}/pic1", status="ready", width=1440, height=900
    )
    get_storage().put("posts", f"post/{asha.pk}/pic1/w1440.webp", b"ASHA-PICTURE-BYTES", "image/webp")
    rup = MediaUpload.objects.create(
        owner=ravi, purpose="post", path=f"post/{ravi.pk}/pic2", status="ready", width=1440, height=900
    )
    get_storage().put("posts", f"post/{ravi.pk}/pic2/w1440.webp", b"RAVI-SECRET-PICTURE", "image/webp")
    return asha, ravi, up, rup


# -- requesting ------------------------------------------------------------------------------------
def test_requesting_an_export_queues_one_and_a_second_is_refused_while_it_runs(two, client_for):
    asha, *_ = two
    r = ask(client_for(asha, email="asha@example.org"))
    assert r.status_code == 202 and r.json()["status"] == "pending" and r.json()["ready_at"] is None
    again = ask(client_for(asha, email="asha@example.org"))
    assert again.status_code == 409 and again.json()["error"]["code"] == "export_in_progress"
    assert DataExport.objects.filter(member=asha).count() == 1
    assert Event.objects.filter(actor=asha, type="export.requested").count() == 1


def test_a_new_export_is_allowed_once_the_last_one_finished(two, client_for):
    asha, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    run_job()
    assert ask(client_for(asha, email="asha@example.org")).status_code == 202
    assert DataExport.objects.filter(member=asha).count() == 2


def test_exports_are_rate_limited(two, client_for, settings):
    asha, *_ = two
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "export": (2, 86400)}
    codes = []
    for _ in range(3):
        codes.append(ask(client_for(asha, email="asha@example.org")).status_code)
        run_job()
    assert codes == [202, 202, 429]


def test_the_status_endpoint_shows_my_latest_export_only(two, client_for):
    asha, ravi, *_ = two
    assert client_for(asha, email="asha@example.org").get("/api/me/export").json() is None
    ask(client_for(asha, email="asha@example.org"))
    assert client_for(asha, email="asha@example.org").get("/api/me/export").json()["status"] == "pending"
    assert client_for(ravi, email="ravi@example.org").get("/api/me/export").json() is None  # never anyone else's


def test_an_export_needs_neither_beta_access_nor_the_latest_consent(two, client_for, beta_on, consent_on):
    asha, *_ = two
    assert (
        ask(client_for(asha, email="asha@example.org")).status_code == 202
    )  # privacy rights do not depend on holding an invite or accepting new terms


# -- what is inside --------------------------------------------------------------------------------
def test_the_zip_holds_only_the_requesters_data(two, client_for):
    asha, ravi, up, rup = two
    ask(client_for(asha, email="asha@example.org"))
    assert run_job()["ready"] == 1
    row = DataExport.objects.get(member=asha)
    assert row.status == "ready" and row.size_bytes > 0 and row.expires_at > timezone.now()
    z = zip_of(row)
    assert sorted(z.namelist()) == ["README.txt", "data.json", f"media/post-{up.pk}.webp"]
    everything = b"".join(z.read(n) for n in z.namelist()).decode(errors="replace")
    for mine in (
        "Asha bio",
        "asha needs help",
        "ASHA-POST",
        "ASHA-REPLY",
        "ASHA-MESSAGE",
        "ASHA-PICTURE-BYTES",
        "asha@example.org",
    ):
        assert mine in everything, mine
    for theirs in ("RAVI-SECRET", "Ravi Menon", "ravi@example.org", "Pune"):
        assert theirs not in everything, theirs  # nothing Ravi wrote, owns or shares: not his messages, notes, posts or picture
    assert f"media/post-{rup.pk}.webp" not in z.namelist()


def test_other_people_appear_as_ids_only(two, client_for):
    asha, ravi, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    run_job()
    data = data_of(DataExport.objects.get(member=asha))
    assert data["connections"][0]["member_id"] == ravi.pk
    assert data["conversations"][0]["with_member_id"] == ravi.pk
    assert [m["body"] for m in data["conversations"][0]["messages_sent"]] == ["ASHA-MESSAGE"]  # only what she sent
    assert data["connection_requests_received"][0] == {**data["connection_requests_received"][0], "sender_id": ravi.pk}
    assert "note" not in data["connection_requests_received"][0]
    assert data["notifications"][0]["payload"]["actor_id"] == ravi.pk


def test_data_json_covers_the_profile_and_my_own_events(two, client_for):
    asha, *_ = two
    client_for(asha, email="asha@example.org").get("/api/me")  # something that records nothing, then something that does
    client_for(asha, email="asha@example.org").patch("/api/me", json.dumps({"city": "Madurai"}), content_type="application/json")
    ask(client_for(asha, email="asha@example.org"))
    run_job()
    data = data_of(DataExport.objects.get(member=asha))
    assert data["profile"]["display_name"] == "Asha Rao" and data["profile"]["city"] == "Madurai"
    assert any(e["type"] == "member.profile_updated" for e in data["events"])
    assert {
        "needs",
        "offers",
        "posts",
        "replies",
        "reactions",
        "follows",
        "applications",
        "circuit_legs",
        "blocks",
        "consents",
    } <= set(data)
    assert "auth_user_id" not in data["profile"]


def test_a_missing_picture_is_listed_not_fatal(two, client_for):
    asha, _, up, _ = two
    get_storage().delete("posts", [f"post/{asha.pk}/pic1/w1440.webp"])
    ask(client_for(asha, email="asha@example.org"))
    assert run_job()["ready"] == 1
    assert data_of(DataExport.objects.get(member=asha))["media_skipped_upload_ids"] == [up.pk]


# -- the email and the link ------------------------------------------------------------------------
def test_the_link_is_emailed_and_trades_for_a_short_storage_url(two, client_for, settings, django_capture_on_commit_callbacks):
    asha, *_ = two
    settings.APP_URL = "https://app.example"
    ask(client_for(asha, email="asha@example.org"))
    with django_capture_on_commit_callbacks(execute=True):
        run_job()
    [msg] = [m for m in mail.outbox if m.to == ["asha@example.org"]]
    assert "24 hours" in msg.body and "https://app.example/settings/export?token=" in msg.body
    token = msg.body.split("token=")[1].split()[0]
    r = client_for(asha, email="asha@example.org").get(f"/api/me/export/download?token={token}")
    assert r.status_code == 200 and r.json()["expires_in"] == settings.EXPORT_DOWNLOAD_SECONDS == 300
    assert r.json()["url"].startswith("https://storage.test/read/private/exports/") and r.json()["size_bytes"] > 0
    assert Event.objects.filter(actor=asha, type="export.downloaded").exists()


def test_someone_elses_link_is_a_404_and_gives_nothing(two, client_for):
    asha, ravi, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    run_job()
    token = export.make_token(DataExport.objects.get(member=asha))
    r = client_for(ravi, email="ravi@example.org").get(
        f"/api/me/export/download?token={token}"
    )  # Ravi found or stole Asha's link
    assert r.status_code == 404 and "exports/" not in r.content.decode()
    assert not Event.objects.filter(type="export.downloaded").exists()


def test_tampered_and_foreign_tokens_are_a_404(two, client_for):
    asha, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    run_job()
    good = export.make_token(DataExport.objects.get(member=asha))
    for bad in (good[:-2] + "xx", "garbage", "", signing.dumps({"e": 1, "m": asha.pk}, salt="other")):
        assert client_for(asha, email="asha@example.org").get(f"/api/me/export/download?token={bad}").status_code == 404, bad


def test_the_link_expires_after_24_hours(two, client_for, monkeypatch):
    asha, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    run_job()
    row = DataExport.objects.get(member=asha)
    fresh = export.make_token(row)
    assert client_for(asha, email="asha@example.org").get(f"/api/me/export/download?token={fresh}").status_code == 200
    minted_at = time.time() - 24 * 3600 - 60
    with monkeypatch.context() as m:  # a link that was minted 24 hours and a minute ago (our own sign-in token must stay valid)
        m.setattr(signing.time, "time", lambda: minted_at)
        old = export.make_token(row)
    r = client_for(asha, email="asha@example.org").get(f"/api/me/export/download?token={old}")
    assert r.status_code == 410 and r.json()["error"]["code"] == "export_expired"


def test_an_expired_export_is_410_even_with_a_fresh_token_and_the_file_is_deleted(two, client_for):
    from apps.accounts import retention

    asha, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    run_job()
    row = DataExport.objects.get(member=asha)
    token, path = export.make_token(row), row.path
    DataExport.objects.filter(pk=row.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert retention.run()["export_files"] == 1
    row.refresh_from_db()
    assert row.status == "expired" and row.path == ""
    with pytest.raises(FileNotFoundError):
        get_storage().get(BUCKET, path)
    assert client_for(asha, email="asha@example.org").get(f"/api/me/export/download?token={token}").status_code == 410
    assert retention.run()["export_files"] == 0  # running again does nothing


def test_download_before_the_job_has_run_is_410(two, client_for):
    asha, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    token = export.make_token(DataExport.objects.get(member=asha))
    assert client_for(asha, email="asha@example.org").get(f"/api/me/export/download?token={token}").status_code == 410


# -- failures and repeats --------------------------------------------------------------------------
def test_a_storage_failure_retries_then_gives_up_without_emailing(two, client_for, monkeypatch):
    asha, *_ = two

    def boom(*a, **kw):
        raise RuntimeError("storage down")

    monkeypatch.setattr(get_storage(), "put", boom)
    ask(client_for(asha, email="asha@example.org"))
    assert [run_job()["retry"], run_job()["retry"], run_job()["failed"]] == [1, 1, 1]
    row = DataExport.objects.get(member=asha)
    assert row.status == "failed" and row.attempts == 3 and not mail.outbox
    assert Event.objects.filter(actor=asha, type="export.failed").exists()
    assert ask(client_for(asha, email="asha@example.org")).status_code == 202  # a failed export does not block the next request


def test_building_the_same_export_twice_is_safe(two, client_for):
    asha, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    row = DataExport.objects.get(member=asha)
    assert export.build_one(row.pk) == "ready" and export.build_one(row.pk) == "skipped"
    assert Event.objects.filter(type="export.ready").count() == 1


def test_the_export_job_logs_counts_only(two, client_for, capfd):
    from django.core.management import call_command

    asha, *_ = two
    ask(client_for(asha, email="asha@example.org"))
    capfd.readouterr()
    call_command("build_exports")
    out = capfd.readouterr().out
    assert "ready=1" in out
    for private in ("Asha", "asha@example.org", "ASHA-", "RAVI"):
        assert private not in out
