"""Stage 7: delete my account. Locked out at once; a job removes the sign-in, files and personal data, shows old content as
"Deleted member", hands over or unclaims startups, keeps what the law or the other people need. Running it twice is safe."""

import json
import uuid
from datetime import date, timedelta

import httpx
import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts import deletion
from apps.accounts.models import Connection, ConnectionRequest, Consent, DataExport, Member, WorkEmailVerification
from apps.beta.models import BetaAccess, InviteCode, WaitlistEntry
from apps.circuits.models import Circuit
from apps.events.models import Event
from apps.intros.models import IntroRequest
from apps.jobs.models import Application, Job
from apps.matching.models import Capability, MatchResult, MemberSkill, MemberTrait, Need, Offer, Trait
from apps.messaging.models import Conversation, Message
from apps.moderation.models import Block, Report
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.social.drop import drop_day
from apps.social.models import DailyDrop, Follow, MediaUpload, Reaction, Reply, UpdateView
from apps.startups.models import Startup, StartupInterest, StartupMember
from core import supabase_admin
from core.models import OutboundEmail
from core.storage import get_storage
from tests.api.test_circuits import make_loop
from tests.api.test_circuits import propose as propose_circuit

pytestmark = pytest.mark.django_db


def delete_me(client):
    return client.post("/api/me/deletion", {"confirm": "DELETE"})


def sign_in(client_for, member):
    """A client whose token carries the member's own email (the default test token has someone else's)."""
    return client_for(member, email=member.email or "someone@example.org")


def run_job():
    return deletion.erase_requested()


@pytest.fixture
def world(lists, make_member, make_org, connect, make_post, make_startup, client_for):
    """Asha is about to leave: she has a profile, content, connections, files, two startups and a circuit in flight."""
    org = make_org()
    asha = make_member(
        "founder", display_name="Asha Rao", email="asha@example.org", bio="ASHA-BIO", city="Chennai", college="KIT", org=org
    )
    ravi, teammate = (
        make_member("mentor", display_name="Ravi Menon", email="ravi@example.org"),
        make_member("founder", display_name="Teammate"),
    )
    connect(asha, ravi)
    cap, trait = Capability.objects.order_by("id").first(), Trait.objects.order_by("id").first()
    Need.objects.create(member=asha, capability=cap)
    Offer.objects.create(member=asha, capability=cap)
    MemberSkill.objects.create(member=asha, capability=cap, level=2)
    MemberTrait.objects.create(member=asha, trait=trait)
    MatchResult.objects.create(member=asha, candidate=ravi, score=0.8, reason="x")
    MatchResult.objects.create(member=ravi, candidate=asha, score=0.8, reason="x")
    ravi_post = make_post(ravi, "everyone", body="Ravi's post")
    asha_post = make_post(asha, "everyone", body="ASHA-POST: pricing notes")
    Reply.objects.create(post=ravi_post, author=asha, body="ASHA-REPLY")
    Reaction.objects.create(post=ravi_post, member=asha, kind="helpful")
    conv = Conversation.objects.create(
        member_a_id=min(asha.pk, ravi.pk), member_b_id=max(asha.pk, ravi.pk), started_by=asha, status="active"
    )
    Message.objects.create(conversation=conv, sender=asha, body="ASHA-MESSAGE to ravi")
    Message.objects.create(conversation=conv, sender=ravi, body="Ravi's reply")
    ConnectionRequest.objects.create(sender=asha, recipient=teammate, note="ASHA-NOTE")
    # startups: one with a teammate (handed over), one alone (unclaimed)
    shared, solo = (
        make_startup(name="Shared Co", domain="shared.io", claimed_by=asha),
        make_startup(name="Solo Co", domain="solo.io", claimed_by=asha),
    )
    solo.claimed_at = timezone.now()
    solo.description = "Solo Co builds soil sensors"
    solo.save()
    for s in (shared, solo):
        StartupMember.objects.create(startup=s, member=asha)
    StartupMember.objects.create(startup=shared, member=teammate)
    solo_job = Job.objects.create(startup=solo, title="Intern", is_open=True, posted_by=asha)
    solo.hiring = True
    solo.save()
    Application.objects.create(
        job=Job.objects.create(startup=shared, title="Dev", posted_by=teammate), student=asha, status="submitted"
    )
    Follow.objects.create(member=asha, startup=shared)
    StartupInterest.objects.create(member=asha, startup=solo)
    # files
    up = MediaUpload.objects.create(
        owner=asha, purpose="post", path=f"post/{asha.pk}/pic1", status="ready", width=1440, height=900
    )
    for name in ("w1440.webp", "w480.webp"):
        get_storage().put("posts", f"{up.path}/{name}", b"ASHA-PIC", "image/webp")
    export = DataExport.objects.create(member=asha, status="ready", path=f"exports/{asha.pk}/old.zip")
    get_storage().put("private", export.path, b"ASHA-ZIP", "application/zip")
    # bookkeeping rows
    notify(asha, "intro.received", actor=ravi, intro_id=1)
    Block.objects.create(blocker=asha, blocked=teammate)
    BetaAccess.objects.create(member=asha, source="code")
    InviteCode.objects.create(code="ASHA-CODE", kind="member", created_by=asha)
    WaitlistEntry.objects.create(email="asha@example.org", role="founder")
    WorkEmailVerification.objects.create(member=asha, email_domain="shared.io", code_hash="x", expires_at=timezone.now())
    DailyDrop.objects.create(member=asha, date=date.today(), candidates=[])
    UpdateView.objects.create(viewer=asha, key="post:1", date=date.today())
    Consent.objects.create(member=asha, policy_version="2026-01", accepted_at=timezone.now())
    Report.objects.create(reporter=asha, target_type="post", target_id=ravi_post.pk, reason="spam")
    OutboundEmail.objects.create(
        to_email="asha@example.org", kind="export.ready", subject="s", body="b", member=asha, next_attempt_at=timezone.now()
    )
    # a circuit in flight with two other people, and a pending intro
    loop = make_loop(make_member)
    loop[0].display_name = "Loop A"
    circuit = propose_circuit(loop)
    intro = IntroRequest.objects.create(
        requester=asha,
        target=ravi,
        message="ASHA-INTRO-TEXT",
        status="pending",
        stage="target",
        expires_at=timezone.now() + timedelta(days=3),
    )
    return {"asha": asha, "ravi": ravi, "teammate": teammate, "shared": shared, "solo": solo, "solo_job": solo_job, "asha_post": asha_post,
            "conv": conv, "up": up, "export": export, "loop": loop, "circuit": circuit, "intro": intro, "org": org}  # fmt: skip


# -- asking ----------------------------------------------------------------------------------------
def test_deleting_needs_the_typed_confirmation(make_member, client_for):
    m = make_member("student")
    c = client_for(m)
    for body in ({}, {"confirm": "delete"}, {"confirm": "yes"}, {"confirm": ""}, {"confirm": True}):
        assert c.post("/api/me/deletion", body).status_code == 422, body
    m.refresh_from_db()
    assert m.deletion_requested_at is None


def test_after_asking_the_account_is_locked_at_once_before_any_job_runs(world, client_for, auth_deletions):
    asha = world["asha"]
    r = delete_me(client_for(asha))
    assert r.status_code == 202 and r.json()["status"] == "scheduled"
    for path in ("/api/me", "/api/matches", "/api/notifications", "/api/me/settings"):
        denied = client_for(asha).get(path)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "account_deleted", path
    assert (
        auth_deletions == [] and Member.objects.get(pk=asha.pk).display_name == "Asha Rao"
    )  # nothing erased yet: the job does that
    assert Event.objects.filter(actor=asha, type="account.deletion_requested").count() == 1


def test_asking_is_about_me_only(world, client_for):
    asha, ravi = world["asha"], world["ravi"]
    delete_me(client_for(ravi))  # there is no id to send: Ravi can only ever ask about himself
    asha.refresh_from_db()
    assert asha.deletion_requested_at is None and Member.objects.get(pk=ravi.pk).deletion_requested_at is not None
    assert client_for(asha).get("/api/me").status_code == 200


def test_a_circuit_admin_cannot_delete_themselves_here(make_member, client_for):
    boss = make_member("super_admin")
    assert delete_me(client_for(boss)).status_code == 403


def test_deleting_needs_neither_beta_access_nor_the_latest_consent(make_member, client_for, beta_on, consent_on):
    assert delete_me(client_for(make_member("student"))).status_code == 202


def test_the_deleted_persons_old_token_cannot_make_a_new_account(world, client_for):
    asha = world["asha"]
    delete_me(client_for(asha))
    run_job()
    before = Member.objects.count()
    r = client_for(asha).get("/api/me")  # the token is still valid for up to an hour
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_deleted"
    assert Member.objects.count() == before  # not re-created as a fresh student (core/auth.py)


# -- what the job does -----------------------------------------------------------------------------
def test_the_job_removes_the_sign_in_and_the_files(world, client_for, auth_deletions):
    asha = world["asha"]
    auth_id = asha.auth_user_id
    delete_me(client_for(asha))
    assert run_job() == {"erased": 1, "failed": 0}
    assert auth_deletions == [auth_id]  # the Supabase user is deleted with the service role
    files = get_storage().files
    assert not any("ASHA" in v.decode() for v in files.values()), "a stored file survived"
    assert ("posts", f"{world['up'].path}/w1440.webp") not in files and ("private", world["export"].path) not in files


def test_the_member_becomes_a_deleted_member_tombstone(world, client_for):
    asha = world["asha"]
    delete_me(client_for(asha))
    run_job()
    t = Member.objects.get(pk=asha.pk)
    assert t.deleted_at is not None
    assert (t.display_name, t.email, t.bio, t.city, t.college) == ("Deleted member", "", "", "", "")
    assert t.location is None and t.organisation_id is None and t.appearance == {} and t.notification_prefs == {}
    assert (t.role, t.verification_level, t.circuits_opt_in, t.visible_to_org, t.is_tester) == ("student", 1, False, False, False)


def test_personal_rows_are_gone(world, client_for):
    asha = world["asha"]
    delete_me(sign_in(client_for, asha))
    run_job()
    for model in (
        Need,
        Offer,
        MemberSkill,
        MemberTrait,
        Reaction,
        Follow,
        StartupInterest,
        Notification,
        DailyDrop,
        BetaAccess,
        WorkEmailVerification,
        DataExport,
        MediaUpload,
        OutboundEmail,
    ):
        field = "owner" if model is MediaUpload else "viewer" if model is UpdateView else "member"
        assert not model.objects.filter(**{field: asha}).exists(), model.__name__
    assert not UpdateView.objects.filter(viewer=asha).exists()
    assert not Application.objects.filter(student=asha).exists() and not StartupMember.objects.filter(member=asha).exists()
    assert not Connection.objects.filter(member_a=asha).exists() and not Connection.objects.filter(member_b=asha).exists()
    assert not ConnectionRequest.objects.filter(sender=asha).exists() and not Block.objects.filter(blocker=asha).exists()
    assert not MatchResult.objects.filter(member=asha).exists() and not MatchResult.objects.filter(candidate=asha).exists()
    assert not WaitlistEntry.objects.filter(email="asha@example.org").exists()
    assert InviteCode.objects.get(code="ASHA-CODE").revoked_at is not None  # her unused invites stop working


def test_old_posts_replies_and_messages_now_read_deleted_member(world, client_for):
    asha, ravi = world["asha"], world["ravi"]
    delete_me(client_for(asha))
    run_job()
    post = client_for(ravi).get(f"/api/posts/{world['asha_post'].pk}")
    assert post.status_code == 200 and post.json()["author"]["display_name"] == "Deleted member"
    replies = client_for(ravi).get(f"/api/posts/{world['asha_post'].pk}/replies").json()
    assert isinstance(replies, list)
    msgs = client_for(ravi).get(f"/api/conversations/{world['conv'].pk}/messages").json()["items"]
    assert {m["body"] for m in msgs} == {
        "ASHA-MESSAGE to ravi",
        "Ravi's reply",
    }  # the other person's conversation still makes sense
    conv = client_for(ravi).get(f"/api/conversations/{world['conv'].pk}").json()
    assert conv["other"]["display_name"] == "Deleted member"
    assert "Asha Rao" not in json.dumps([post.json(), replies, msgs, conv])


def test_the_tombstone_cannot_be_found_messaged_or_matched(world, client_for):
    asha, ravi = world["asha"], world["ravi"]
    delete_me(client_for(asha))
    run_job()
    c = client_for(ravi)
    assert c.get(f"/api/members/{asha.pk}").status_code == 404
    assert c.post("/api/conversations", {"member_id": asha.pk, "body": "hi"}).status_code == 404
    assert c.post("/api/connections/requests", {"member_id": asha.pk, "note": ""}).status_code == 404
    assert c.post("/api/intros", {"target_id": asha.pk, "message": "hi"}).status_code == 404
    assert asha.pk not in {m["candidate_id"] for m in c.get("/api/matches").json()["items"]}


def test_a_startup_goes_to_a_teammate_or_becomes_unclaimed_and_its_data_stays(world, client_for, monkeypatch):
    asha, teammate = world["asha"], world["teammate"]
    seen = []
    monkeypatch.setattr(
        deletion, "on_startup_unclaimed", lambda startup, transferred_to=None: seen.append((startup.pk, transferred_to))
    )
    delete_me(client_for(asha))
    run_job()
    shared, solo = Startup.objects.get(pk=world["shared"].pk), Startup.objects.get(pk=world["solo"].pk)
    assert shared.claimed_by_id == teammate.pk  # handed to the other team member
    assert solo.claimed_by_id is None and solo.claimed_at is None  # nobody left: unclaimed again
    assert solo.name == "Solo Co" and solo.description == "Solo Co builds soil sensors"  # the profile is never wiped
    assert sorted(seen) == sorted(
        [(shared.pk, teammate.pk), (solo.pk, None)]
    )  # the hook where promotions pause a campaign (Stage 4d)
    job = Job.objects.get(pk=world["solo_job"].pk)
    assert job.is_open is False and solo.hiring is False  # nobody manages the roles she posted any more


def test_circuits_and_intros_in_flight_end_without_naming_anyone(world, client_for):
    asha = world["asha"]
    a, b, c = world["loop"]
    Notification.objects.all().delete()
    # put Asha into the loop's circuit as one of its members
    from apps.circuits.models import CircuitLeg

    CircuitLeg.objects.filter(circuit=world["circuit"], giver=a).update(giver=asha)
    delete_me(client_for(asha))
    run_job()
    assert Circuit.objects.get(pk=world["circuit"].pk).status == "declined"
    notes = list(Notification.objects.filter(kind="circuit.declined"))
    assert {n.member_id for n in notes} == {b.pk, c.pk} and all("actor_id" not in n.payload for n in notes)
    intro = IntroRequest.objects.get(pk=world["intro"].pk)
    assert (intro.status, intro.stage, intro.message) == ("expired", "stopped", "")


def test_what_has_to_stay_stays(world, client_for):
    asha = world["asha"]
    events_before = Event.objects.filter(actor=asha).count()
    delete_me(client_for(asha))
    run_job()
    assert Member.objects.filter(pk=asha.pk).exists()  # the row is never deleted: orders and payments (Stage 4e) point at it
    assert Event.objects.filter(actor=asha).count() >= events_before  # events stay, pseudonymous: ids and enums only
    assert Consent.objects.filter(member=asha).exists() and Report.objects.filter(reporter=asha).exists()
    assert Event.objects.filter(type="account.deleted", target_id=asha.pk).exists()
    from django.conf import settings

    assert settings.FINANCIAL_RECORD_RETENTION_YEARS == 8  # the period the accountant must confirm


def test_other_peoples_data_is_untouched(world, client_for):
    asha, ravi = world["asha"], world["ravi"]
    delete_me(client_for(asha))
    run_job()
    r = Member.objects.get(pk=ravi.pk)
    assert (r.display_name, r.email, r.deleted_at) == ("Ravi Menon", "ravi@example.org", None)
    assert Message.objects.filter(sender=ravi).count() == 1 and client_for(ravi).get("/api/me").status_code == 200


# -- idempotent and failure-safe -------------------------------------------------------------------
def test_running_the_job_twice_is_safe(world, client_for, auth_deletions):
    asha = world["asha"]
    delete_me(client_for(asha))
    assert run_job() == {"erased": 1, "failed": 0}
    snapshot = (Member.objects.get(pk=asha.pk).deleted_at, Event.objects.count(), Notification.objects.count())
    assert run_job() == {"erased": 0, "failed": 0}
    assert deletion.erase(Member.objects.get(pk=asha.pk)) == "already"
    assert (Member.objects.get(pk=asha.pk).deleted_at, Event.objects.count(), Notification.objects.count()) == snapshot
    assert len(auth_deletions) == 1 and Event.objects.filter(type="account.deleted").count() == 1


def test_asking_twice_is_safe(world, client_for):
    asha = world["asha"]
    assert delete_me(client_for(asha)).status_code == 202
    first = Member.objects.get(pk=asha.pk).deletion_requested_at
    deletion.request_deletion(Member.objects.get(pk=asha.pk))
    assert Member.objects.get(pk=asha.pk).deletion_requested_at == first
    assert Event.objects.filter(type="account.deletion_requested").count() == 1


def test_if_supabase_is_down_the_account_stays_locked_and_the_next_run_finishes(world, client_for):
    asha = world["asha"]
    delete_me(client_for(asha))

    def down(auth_user_id):
        raise supabase_admin.AuthDeleteFailed("HTTP 503")

    supabase_admin.set_deleter(down)
    assert run_job() == {"erased": 0, "failed": 1}
    t = Member.objects.get(pk=asha.pk)
    assert (
        t.deleted_at is None and t.display_name == "Asha Rao" and Need.objects.filter(member=asha).exists()
    )  # nothing half-done
    assert client_for(asha).get("/api/me").status_code == 403  # and still locked out
    supabase_admin.set_deleter(lambda auth_user_id: True)
    assert run_job() == {"erased": 1, "failed": 0}


def test_a_user_already_gone_from_supabase_counts_as_deleted(world, client_for, monkeypatch, settings):
    asha = world["asha"]
    delete_me(client_for(asha))  # sign in first: the test token is checked against the test project's URL
    settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY = "https://x.supabase.co", "service"
    supabase_admin.set_deleter(None)
    calls = []

    class Gone:
        status_code = 404

    monkeypatch.setattr(httpx, "delete", lambda url, **kw: calls.append((url, kw["headers"]["Authorization"])) or Gone())
    assert run_job() == {"erased": 1, "failed": 0}
    assert calls == [(f"https://x.supabase.co/auth/v1/admin/users/{asha.auth_user_id}", "Bearer service")]


def test_supabase_5xx_is_retried_then_reported(monkeypatch, settings):
    settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY = "https://x.supabase.co", "service"
    supabase_admin.set_deleter(None)
    monkeypatch.setattr(supabase_admin.time, "sleep", lambda s: None)
    attempts = []

    class Down:
        status_code = 503

    monkeypatch.setattr(httpx, "delete", lambda url, **kw: attempts.append(1) or Down())
    with pytest.raises(supabase_admin.AuthDeleteFailed):
        supabase_admin.delete_auth_user(uuid.uuid4())
    assert len(attempts) == supabase_admin.ATTEMPTS == 3


def test_a_storage_failure_leaves_the_account_locked_for_the_next_run(world, client_for, monkeypatch):
    asha = world["asha"]
    delete_me(client_for(asha))
    storage = get_storage()
    real = storage.delete
    monkeypatch.setattr(storage, "delete", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("storage down")))
    assert run_job() == {"erased": 0, "failed": 1}
    assert Member.objects.get(pk=asha.pk).deleted_at is None
    monkeypatch.setattr(storage, "delete", real)
    assert run_job() == {"erased": 1, "failed": 0}


def test_dev_without_supabase_still_erases(world, client_for, settings):
    delete_me(client_for(world["asha"]))
    settings.SUPABASE_URL = settings.SUPABASE_SERVICE_ROLE_KEY = ""
    supabase_admin.set_deleter(None)
    assert run_job() == {"erased": 1, "failed": 0}


def test_the_job_logs_no_personal_data(world, client_for, capfd):
    asha = world["asha"]
    delete_me(client_for(asha))
    capfd.readouterr()
    call_command("delete_accounts")
    out = capfd.readouterr().out
    assert "erased=1" in out
    for private in ("Asha", "asha@example.org", "ASHA-", "Chennai", "KIT"):
        assert private not in out
    assert "account_erased" in out


def test_the_dev_command_refuses_outside_dev_and_needs_confirmation(world, settings):
    from django.core.management.base import CommandError

    settings.ENV = "production"
    with pytest.raises(CommandError, match="local development only"):
        call_command("delete_member", member=world["asha"].pk, yes=True)
    settings.ENV = "dev"
    call_command("delete_member", member=world["asha"].pk, yes=True)
    assert Member.objects.get(pk=world["asha"].pk).deleted_at is not None


def test_a_deleted_member_vanishes_from_other_peoples_todays_drop(world, client_for):
    asha, ravi = world["asha"], world["ravi"]
    card = {"member_id": asha.pk, "reason": "shared", "is_bridge": False, "outcome": None, "strength": "good"}
    DailyDrop.objects.create(member=ravi, date=drop_day(timezone.now()), candidates=[card])
    assert [c["member"]["id"] for c in client_for(ravi).get("/api/drop/today").json()["cards"]] == [asha.pk]
    delete_me(client_for(asha))
    run_job()
    assert client_for(ravi).get("/api/drop/today").json()["cards"] == []
