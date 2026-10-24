"""Stages 6-7 IDOR: member A cannot read, change, export or delete anything of member B's through any account endpoint."""

import json

import pytest

from apps.accounts import export
from apps.accounts.models import Consent, DataExport, Member
from apps.matching.models import Capability, Need
from apps.moderation.models import Block
from apps.notifications.models import Notification
from apps.notifications.services import notify
from core.models import OutboundEmail

pytestmark = pytest.mark.django_db
B_SECRETS = ("Bhavna Private", "bhavna@example.org", "BHAVNA-BIO", "BHAVNA-NEED")


@pytest.fixture
def pair(make_member, client_for):
    a = make_member("founder", display_name="Anil A", email="anil@example.org")
    b = make_member(
        "founder", display_name="Bhavna Private", email="bhavna@example.org", bio="BHAVNA-BIO", city="Kochi",
        appearance={"theme": "dark", "accent": "lime", "swipe_tabs": False},
        notification_prefs={"intros": {"in_app": True, "email": False}},
    )  # fmt: skip
    Need.objects.create(member=b, capability=Capability.objects.order_by("id").first(), description="BHAVNA-NEED")
    Consent.objects.create(member=b, policy_version="2026-01", accepted_at=b.created_at)
    Block.objects.create(blocker=b, blocked=make_member("student"))
    notify(b, "application.status", application_id=1)
    client_for(b, email="bhavna@example.org").post("/api/me/export")
    export.build_pending()
    return a, b


def snapshot(b):
    m = Member.objects.get(pk=b.pk)
    return {
        "member": {f.name: getattr(m, f.name) for f in Member._meta.concrete_fields if f.name not in ("updated_at", "location")},
        "needs": list(Need.objects.filter(member=b).values_list("pk", "description")),
        "consents": Consent.objects.filter(member=b).count(),
        "blocks": Block.objects.filter(blocker=b).count(),
        "notifications": list(Notification.objects.filter(member=b).values_list("pk", "read_at")),
        "exports": list(DataExport.objects.filter(member=b).values_list("pk", "status", "path")),
        "emails": OutboundEmail.objects.filter(member=b).count(),
    }


def test_a_can_do_everything_to_their_own_account_and_none_of_it_touches_b(pair, client_for):
    a, b = pair
    before = snapshot(b)
    c = client_for(a, email="anil@example.org")
    body = lambda d: json.dumps(d)  # noqa: E731
    responses = [
        c.get("/api/me"),
        c.get("/api/me/settings"),
        c.patch("/api/me", body({"display_name": "Anil Changed", "bio": "changed"}), content_type="application/json"),
        c.patch(
            "/api/me/privacy", body({"profile_visibility": "hidden", "allow_requests": False}), content_type="application/json"
        ),
        c.patch(
            "/api/me/appearance", body({"accent": "rose", "theme": "light", "swipe_tabs": True}), content_type="application/json"
        ),
        c.patch(
            "/api/me/notification-preferences",
            body({"intros": {"email": True, "in_app": False}}),
            content_type="application/json",
        ),
        c.post("/api/me/consent", {"policy_version": "2026-01"}),
        c.get("/api/me/blocks"),
        c.post("/api/me/export"),
        c.get("/api/me/export"),
        c.get("/api/notifications"),
        c.post("/api/notifications/read-all"),
        c.post("/api/support", {"kind": "question", "message": "Hello, a question"}),
    ]
    assert [r.status_code for r in responses if r.status_code >= 400] == []
    export.build_pending()
    c.post("/api/me/deletion", {"confirm": "DELETE"})
    from apps.accounts import deletion

    deletion.erase_requested()
    assert Member.objects.get(pk=a.pk).deleted_at is not None
    for r in responses:
        text = r.content.decode()
        assert not any(secret in text for secret in B_SECRETS), r.request["PATH_INFO"]
    assert snapshot(b) == before  # not a single field, row, setting, file or email of B's changed


def test_a_cannot_reach_b_by_id_anywhere(pair, client_for):
    a, b = pair
    c = client_for(a, email="anil@example.org")
    b_note = Notification.objects.get(member=b)
    b_export = DataExport.objects.get(member=b)
    token = export.make_token(b_export)
    checks = {
        "read b's notification": c.post(f"/api/notifications/{b_note.pk}/read"),
        "download b's export with b's link": c.get(f"/api/me/export/download?token={token}"),
        "unblock one of b's blocks": c.delete(f"/api/members/{Block.objects.get(blocker=b).blocked_id}/block"),
    }
    assert [(k, r.status_code) for k, r in checks.items()] == [(k, 404) for k in checks]
    assert Notification.objects.get(pk=b_note.pk).read_at is None and Block.objects.filter(blocker=b).count() == 1
    assert not any(secret in r.content.decode() for r in checks.values() for secret in B_SECRETS)


def test_b_does_not_appear_in_as_settings_or_blocks_or_export(pair, client_for):
    a, b = pair
    c = client_for(a, email="anil@example.org")
    settings = c.get("/api/me/settings").json()
    assert (
        settings["profile"]["display_name"] == "Anil A"
        and settings["appearance"]["accent"] == "mint"
        and settings["blocked_count"] == 0
    )
    assert settings["export"] is None  # b's finished export is not a's
    c.post("/api/me/export")
    export.build_pending()
    assert DataExport.objects.get(member=a).path != DataExport.objects.get(member=b).path
    assert c.get("/api/me/blocks").json() == {"items": []}
