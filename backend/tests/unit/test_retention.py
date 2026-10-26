"""Stage 7: `manage.py retention_cleanup` removes only what it should: accounts that never accepted the terms (30 days), expired
export files, old rejected waitlist entries. Idempotent. Logs counts only."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.accounts import retention
from apps.accounts.models import Consent, DataExport, Member
from apps.beta.models import WaitlistEntry
from apps.events.models import Event
from apps.notifications.models import Notification
from core import supabase_admin
from core.storage import get_storage

pytestmark = pytest.mark.django_db

NONE = dict.fromkeys(
    ("unverified_accounts", "export_files", "waitlist_entries", "ranker_snapshots", "events", "notifications", "webhook_events"),
    0,
)  # what run() reports when there was nothing to remove


def aged(member, days=0, seconds=0):
    Member.objects.filter(pk=member.pk).update(created_at=timezone.now() - timedelta(days=days, seconds=seconds))
    return member


def consent(member, version="2026-01"):
    return Consent.objects.create(member=member, policy_version=version, accepted_at=timezone.now())


def exists(member):
    return Member.objects.get(pk=member.pk).deleted_at is None


# -- unverified accounts ---------------------------------------------------------------------------
def test_an_account_that_never_accepted_the_terms_is_purged_after_30_days(make_member, auth_deletions):
    stale = aged(make_member("student", email="gone@example.org", display_name="Never Accepted"), days=31)
    assert retention.run()["unverified_accounts"] == 1
    t = Member.objects.get(pk=stale.pk)
    assert t.deleted_at is not None and t.display_name == "Deleted member" and t.email == ""
    assert auth_deletions == [
        stale.auth_user_id
    ]  # the Supabase sign-in goes too, through the same pipeline as "delete my account"


def test_the_boundary_is_exactly_30_days(make_member):
    just_inside = aged(make_member("student"), days=30, seconds=-60)
    just_outside = aged(make_member("student"), days=30, seconds=60)
    retention.run()
    assert exists(just_inside) and not exists(just_outside)


def test_everyone_who_accepted_anything_is_kept(make_member):
    old_version = aged(make_member("student"), days=400)
    current = aged(make_member("founder"), days=400)
    consent(old_version, "2024-01")  # they did get past the Welcome screen once: not "unverified"
    consent(current)
    retention.run()
    assert exists(old_version) and exists(current)


def test_staff_are_never_purged(make_member, make_org):
    admin_member = aged(make_member("super_admin"), days=400)
    partner = aged(make_member("partner_admin", org=make_org()), days=400)
    retention.run()
    assert exists(admin_member) and exists(partner)


def test_new_members_and_already_deleted_ones_are_left_alone(make_member, auth_deletions):
    fresh = aged(make_member("student"), days=2)
    aged(make_member("student", deleted_at=timezone.now()), days=400)  # a tombstone already: not processed again
    assert retention.run()["unverified_accounts"] == 0
    assert exists(fresh) and auth_deletions == []


def test_a_stuck_account_does_not_stop_the_rest(make_member):
    first, second = (aged(make_member("student"), days=60) for _ in range(2))

    def flaky(auth_user_id):
        if auth_user_id == first.auth_user_id:
            raise supabase_admin.AuthDeleteFailed("HTTP 503")
        return True

    supabase_admin.set_deleter(flaky)
    assert retention.run()["unverified_accounts"] == 1
    assert Member.objects.get(pk=first.pk).deleted_at is None and not exists(second)  # the first stays locked for the next run
    assert Member.objects.get(pk=first.pk).deletion_requested_at is not None  # already locked out while it waits
    supabase_admin.set_deleter(lambda auth_user_id: True)
    assert retention.run()["unverified_accounts"] == 1  # the next run finishes it
    assert not exists(first)


# -- export files ----------------------------------------------------------------------------------
def test_only_expired_export_files_are_deleted(make_member):
    m = make_member("student")
    store = get_storage()
    rows = {}
    for name, status, delta in (("old", "ready", -1), ("fresh", "ready", 5), ("queued", "pending", None)):
        path = f"exports/{m.pk}/{name}.zip"
        store.put("private", path, b"zip", "application/zip")
        rows[name] = DataExport.objects.create(
            member=m, status=status, path=path, expires_at=None if delta is None else timezone.now() + timedelta(hours=delta)
        )
        if name == "queued":
            DataExport.objects.filter(pk=rows[name].pk).update(status="pending")
    assert retention.run()["export_files"] == 1
    assert ("private", rows["old"].path) not in store.files
    assert ("private", rows["fresh"].path) in store.files and ("private", rows["queued"].path) in store.files
    rows["old"].refresh_from_db()
    assert rows["old"].status == "expired" and rows["old"].path == ""


# -- waitlist --------------------------------------------------------------------------------------
def entry(email, status, reviewed_days=None, created_days=0):
    e = WaitlistEntry.objects.create(email=email, role="student", status=status)
    WaitlistEntry.objects.filter(pk=e.pk).update(
        reviewed_at=None if reviewed_days is None else timezone.now() - timedelta(days=reviewed_days),
        created_at=timezone.now() - timedelta(days=created_days),
    )
    return e


def test_only_old_rejected_waitlist_entries_go(settings):
    gone = entry("a@example.org", "rejected", reviewed_days=91)
    gone_unreviewed = entry(
        "b@example.org", "rejected", reviewed_days=None, created_days=200
    )  # rejected with no review time: use creation
    recent = entry("c@example.org", "rejected", reviewed_days=89)
    pending = entry("d@example.org", "pending", created_days=500)
    approved = entry("e@example.org", "approved", reviewed_days=500)
    assert retention.run()["waitlist_entries"] == 2
    kept = set(WaitlistEntry.objects.values_list("pk", flat=True))
    assert kept == {recent.pk, pending.pk, approved.pk} and gone.pk not in kept and gone_unreviewed.pk not in kept


# -- the job as a whole ----------------------------------------------------------------------------
def test_running_it_twice_changes_nothing_the_second_time(make_member):
    aged(make_member("student"), days=60)
    entry("a@example.org", "rejected", reviewed_days=200)
    first = retention.run()
    assert first == {**NONE, "unverified_accounts": 1, "waitlist_entries": 1}
    assert retention.run() == NONE


def test_nothing_to_do_is_fine(db):
    assert retention.run() == NONE


def test_it_logs_counts_only_and_records_one_event(make_member, capfd):
    aged(make_member("student", email="private.person@example.org", display_name="Private Person", bio="PRIVATE-BIO"), days=60)
    entry("waiter@example.org", "rejected", reviewed_days=200)
    capfd.readouterr()
    call_command("retention_cleanup")
    out = capfd.readouterr().out
    assert "unverified_accounts=1" in out and "retention_cleanup" in out
    for private in ("private.person", "Private Person", "PRIVATE-BIO", "waiter@example.org"):
        assert private not in out
    event = Event.objects.get(type="retention.cleaned")
    assert event.payload == {"counts": {**NONE, "unverified_accounts": 1, "waitlist_entries": 1}} and event.actor_id is None


# -- free-tier housekeeping: events, notifications, webhook records ------------------------------------
def old_event(days, type_="post.created"):
    """The events table refuses UPDATE, so an old row is inserted with its date."""
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO events_event (type, target_type, payload, created_at) VALUES (%s, '', '{}', now() - make_interval(days => %s))",
            [type_, days],
        )


def test_events_older_than_a_year_go_and_newer_ones_stay():
    old_event(400)
    old_event(366)
    old_event(364)
    old_event(1)
    assert retention.purge_events() == 2
    assert Event.objects.filter(type="post.created").count() == 2


def test_events_stay_append_only_for_everyone_else():
    old_event(400)
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        Event.objects.filter(type="post.created").delete()
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        Event.objects.filter(type="post.created").update(payload={"x": 1})
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic(), connection.cursor() as cur:
        cur.execute("DELETE FROM events_event")  # the permission to purge lasts for one transaction only
    assert retention.purge_events() == 1


def test_events_are_purged_in_batches(monkeypatch):
    monkeypatch.setattr(retention, "BATCH", 2)
    for _ in range(5):
        old_event(500)
    assert retention.purge_events() == 5


def test_notifications_read_ones_after_90_days_and_any_after_180(make_member):
    m = make_member("student")
    now = timezone.now()

    def note(days, read):
        n = Notification.objects.create(member=m, kind="intro.received")
        Notification.objects.filter(pk=n.pk).update(created_at=now - timedelta(days=days), read_at=now if read else None)
        return n.pk

    keep = {note(30, True), note(89, True), note(100, False), note(179, False)}
    note(91, True)
    note(181, False)
    note(400, True)
    assert retention.purge_notifications() == 3
    assert set(Notification.objects.values_list("pk", flat=True)) == keep


def test_webhook_records_are_skipped_until_the_payments_app_exists():
    assert retention.purge_webhook_events() == 0


def test_webhook_records_older_than_90_days_go_when_the_model_exists(monkeypatch):
    class FakeModel:
        class objects:  # noqa: N801
            @staticmethod
            def filter(**kw):
                FakeModel.seen = kw
                return Notification.objects.none()

    monkeypatch.setattr(retention.apps, "get_model", lambda app, name: FakeModel)
    assert retention.purge_webhook_events() == 0
    assert "received_at__lt" in FakeModel.seen


def test_retention_periods_are_the_documented_ones(settings):
    assert (settings.EVENT_RETENTION_DAYS, settings.NOTIFICATION_READ_RETENTION_DAYS, settings.NOTIFICATION_RETENTION_DAYS) == (
        365,
        90,
        180,
    )
    assert (settings.WEBHOOK_EVENT_RETENTION_DAYS, settings.RANKER_SNAPSHOT_RETENTION_DAYS) == (90, 365)
