"""Stages 6-7: no names, emails, phones, tokens or free text in log output from any new endpoint or job (CLAUDE.md privacy rules)."""

import json

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from apps.accounts import export
from apps.accounts.models import DataExport
from apps.notifications import unsubscribe
from apps.notifications.services import notify
from core.models import OutboundEmail

pytestmark = pytest.mark.django_db

NAME, EMAIL, BIO, PHONE, NOTE = (
    "Zainab Quraishi",
    "zainab.private@example.org",
    "ZAINAB-PRIVATE-BIO",
    "9812345678",
    "ZAINAB-FREE-TEXT-NOTE",
)
OTHER = "Dhruv Unrelated"
SECRETS = [NAME, EMAIL, BIO, PHONE, NOTE, OTHER, "Zainab", "zainab.private"]


def patch(c, path, body):
    return c.patch(path, json.dumps(body), content_type="application/json")


def test_no_personal_data_in_logs_from_any_new_endpoint(make_member, connect, token_for, capfd, settings):
    me = make_member("founder", display_name=NAME, bio=BIO, email=EMAIL, level=2)
    other = make_member("mentor", display_name=OTHER)
    connect(me, other)
    token = token_for(me, email=EMAIL, user_metadata={"full_name": NAME, "phone": PHONE})
    c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")
    capfd.readouterr()

    calls = [
        c.get("/api/me"),
        c.get("/api/me/settings"),
        patch(c, "/api/me", {"display_name": NAME, "bio": BIO}),
        patch(c, "/api/me/privacy", {"profile_visibility": "hidden", "visible_to_org": True}),
        patch(c, "/api/me/privacy", {"profile_visibility": "everyone"}),  # a validation error that echoes input
        patch(c, "/api/me/appearance", {"accent": "rose", "theme": EMAIL}),  # 422 with the bad value in the details
        patch(c, "/api/me/notification-preferences", {"intros": {"email": False}}),
        c.post("/api/me/consent", json.dumps({"policy_version": settings.POLICY_VERSION}), content_type="application/json"),
        c.post(
            "/api/support",
            json.dumps({"kind": "grievance", "message": f"{NOTE} {PHONE} {EMAIL}"}),
            content_type="application/json",
        ),
        c.get("/api/notifications"),
        c.post(f"/api/members/{other.pk}/block"),
        c.get("/api/me/blocks"),
        c.delete(f"/api/members/{other.pk}/block"),
        c.post(
            "/api/reports",
            json.dumps({"target_type": "member", "target_id": other.pk, "reason": f"{NOTE} {EMAIL}"}),
            content_type="application/json",
        ),
        c.post("/api/me/export"),
        c.get("/api/me/export"),
        c.get("/api/me/export/download?token=" + EMAIL),
    ]
    assert all(r.status_code < 500 for r in calls)
    notify(me, "application.status", actor=other, application_id=1)
    token_link = (
        OutboundEmail.objects.get(kind="notification.applications").headers["List-Unsubscribe"].split("token=")[1].rstrip(">")
    )
    Client().post(f"/api/unsubscribe?token={token_link}")
    Client().get(f"/api/unsubscribe?token={token_link}x")  # tampered: 400
    Client().get("/api/unsubscribe?token=" + EMAIL)
    out = capfd.readouterr().out
    assert out, "expected log output"
    for secret in [*SECRETS, token, token.split(".")[1], token_link]:
        assert secret not in out, f"{secret!r} leaked into logs"
    assert not [x for x in out.splitlines() if x.startswith("{") and '"event": "request"' not in x and EMAIL in x]


def test_no_personal_data_in_logs_from_the_new_jobs(make_member, connect, capfd, client_for):
    me = make_member("founder", display_name=NAME, bio=BIO, email=EMAIL, city="Madurai")
    gone = make_member("student", display_name="Leaving Person", email="leaving@example.org", bio="LEAVING-BIO")
    stale = make_member("student", display_name="Stale Person", email="stale@example.org")
    type(stale).objects.filter(pk=stale.pk).update(created_at=timezone.now() - timezone.timedelta(days=90))
    notify(me, "intro.received", intro_id=1)
    client_for(me, email=EMAIL).post("/api/me/export")
    client_for(gone, email="leaving@example.org").post("/api/me/deletion", {"confirm": "DELETE"})
    capfd.readouterr()
    for job in ("build_exports", "delete_accounts", "retention_cleanup", "send_emails"):
        call_command(job)
    out = capfd.readouterr().out
    assert DataExport.objects.get(member=me).status == "ready" and out
    for secret in (*SECRETS, "Leaving", "leaving@example.org", "LEAVING-BIO", "Stale", "stale@example.org", "Madurai"):
        assert secret not in out, f"{secret!r} leaked into job output"


def test_the_export_zip_never_contains_a_token_or_another_members_email(make_member, client_for):
    me = make_member("founder", display_name=NAME, email=EMAIL)
    other = make_member("mentor", display_name=OTHER, email="dhruv@example.org")
    client_for(me, email=EMAIL).post("/api/me/export")
    export.build_pending()
    import io
    import zipfile

    from core.storage import get_storage

    row = DataExport.objects.get(member=me)
    text = zipfile.ZipFile(io.BytesIO(get_storage().get("private", row.path))).read("data.json").decode()
    assert EMAIL in text and "dhruv@example.org" not in text and OTHER not in text and str(other.auth_user_id) not in text
    assert unsubscribe.SALT not in text and "eyJ" not in text  # no token-looking strings
