"""Job health: every scheduled job records its last success and last error, `check_jobs` reports the overdue ones,
and super admins can read the same list at GET /api/health/jobs."""

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from core import jobhealth, jobs
from core.models import JobRun

pytestmark = pytest.mark.django_db


class Boom(jobs.JobCommand):
    """A job that fails with an email address in its message, which must never be stored as typed."""

    def run(self):
        raise ValueError("cannot send to asha@example.com using token eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl")


class Fine(jobs.JobCommand):
    def run(self):
        return {"things": 3}


class Nothing(jobs.JobCommand):
    def run(self):
        return {"skip_reason": "nothing to do"}


def run(cls, name):
    cls.__module__ = f"apps.fake.{name}"  # the job's name is its module's last part
    cls().handle()


@pytest.fixture
def intervals(settings):
    settings.JOB_INTERVALS = {"expire_items": 5, "compute_matches": 1440, "run_circuit_round": 10080}
    return settings.JOB_INTERVALS


def by_name(rows):
    return {r.name: r for r in rows}


# ---- recording -------------------------------------------------------------------------------------------------------------


def test_success_sets_last_success_and_clears_the_error():
    JobRun.objects.create(name="fine", running_until=timezone.now(), last_error="OldError: x")
    run(Fine, "fine")
    row = JobRun.objects.get(name="fine")
    assert row.last_status == "ok" and row.last_success_at and row.last_error == ""


def test_a_job_that_found_nothing_to_do_still_counts_as_a_success():
    run(Nothing, "nothing")
    row = JobRun.objects.get(name="nothing")
    assert row.last_status == "skipped" and row.last_success_at is not None


def test_failure_records_the_error_without_the_email_or_token_and_keeps_the_last_success():
    earlier = timezone.now() - timedelta(hours=3)
    JobRun.objects.create(name="boom", running_until=earlier, last_success_at=earlier)
    with pytest.raises(ValueError):
        run(Boom, "boom")
    row = JobRun.objects.get(name="boom")
    assert row.last_status == "failed" and row.last_success_at == earlier
    assert row.last_error.startswith("ValueError: cannot send to")
    assert "asha@example.com" not in row.last_error and "eyJ" not in row.last_error
    assert len(row.last_error) <= 200


def test_the_next_success_clears_the_error():
    with pytest.raises(ValueError):
        run(Boom, "retry")
    run(Fine, "retry")
    assert JobRun.objects.get(name="retry").last_error == ""


# ---- overdue ---------------------------------------------------------------------------------------------------------------


def test_nothing_is_expected_when_no_intervals_are_configured(settings):
    settings.JOB_INTERVALS = {}
    assert jobhealth.status() == []


def test_a_fresh_success_is_on_time_and_twice_the_interval_is_the_limit(intervals):
    now = timezone.now()
    JobRun.objects.create(name="expire_items", running_until=now, last_success_at=now - timedelta(minutes=9), first_seen_at=now)
    JobRun.objects.create(name="compute_matches", running_until=now, last_success_at=now - timedelta(hours=47), first_seen_at=now)
    rows = by_name(jobhealth.status(now))
    assert not rows["expire_items"].overdue and not rows["compute_matches"].overdue
    JobRun.objects.filter(name="expire_items").update(last_success_at=now - timedelta(minutes=11))
    JobRun.objects.filter(name="compute_matches").update(last_success_at=now - timedelta(hours=49))
    rows = by_name(jobhealth.status(now))
    assert rows["expire_items"].overdue and "expected every 5m" in rows["expire_items"].reason
    assert (
        rows["compute_matches"].overdue
        and "2d" in rows["compute_matches"].reason
        and "expected every 1d" in rows["compute_matches"].reason
    )


def test_a_job_that_never_succeeded_is_judged_from_when_it_was_first_seen(intervals):
    now = timezone.now()
    JobRun.objects.create(name="expire_items", running_until=now, first_seen_at=now - timedelta(minutes=30))
    row = by_name(jobhealth.status(now))["expire_items"]
    assert row.overdue and row.reason.startswith("never succeeded")
    JobRun.objects.filter(name="expire_items").update(first_seen_at=now - timedelta(minutes=3))
    assert not by_name(jobhealth.status(now))["expire_items"].overdue


def test_a_job_with_no_row_yet_is_not_overdue_until_check_jobs_starts_its_clock(intervals):
    row = by_name(jobhealth.status())["expire_items"]
    assert not row.overdue and row.reason == "never ran"
    assert jobhealth.ensure_rows() == 3
    assert JobRun.objects.filter(name="expire_items").exists()
    assert jobhealth.ensure_rows() == 0  # again: nothing new


def test_a_job_whose_flag_is_off_is_never_overdue(intervals, settings):
    old = timezone.now() - timedelta(days=30)
    JobRun.objects.create(name="run_circuit_round", running_until=old, first_seen_at=old)
    assert by_name(jobhealth.status())["run_circuit_round"].overdue  # circuits on: silent for 30 days is a problem
    settings.FEATURES = "circuits:off"
    row = by_name(jobhealth.status())["run_circuit_round"]
    assert not row.overdue and row.reason == "flag off"


# ---- check_jobs ------------------------------------------------------------------------------------------------------------


def test_check_jobs_logs_each_overdue_job_by_name_and_ends_with_its_heartbeat(intervals, capfd):
    old = timezone.now() - timedelta(hours=2)
    JobRun.objects.create(name="expire_items", running_until=old, first_seen_at=old)
    call_command("check_jobs")
    lines = [json.loads(line) for line in capfd.readouterr().out.splitlines() if line.startswith("{")]
    late = [line for line in lines if line.get("event") == "job.overdue"]
    assert [line["job"] for line in late] == ["expire_items"] and late[0]["severity"] == "ERROR"
    end = [line for line in lines if line.get("event") == "job.end" and line.get("job") == "check_jobs"]
    assert end and end[0]["overdue"] == 1 and end[0]["jobs_watched"] == 3  # the heartbeat the alert waits for


def test_check_jobs_is_quiet_when_everything_is_on_time(intervals, capfd):
    call_command("check_jobs")
    out = capfd.readouterr().out
    assert "job.overdue" not in out


# ---- GET /api/health/jobs --------------------------------------------------------------------------------------------------


def test_endpoint_is_for_super_admins_only(intervals, make_member, client_for):
    assert client_for().get("/api/health/jobs").status_code == 401
    for role in ("student", "founder", "mentor", "investor", "partner_admin"):
        r = client_for(make_member(role)).get("/api/health/jobs")
        assert r.status_code == 403, role
        assert r.json()["error"]["code"]


def test_endpoint_lists_jobs_for_a_super_admin(intervals, make_member, client_for):
    now = timezone.now()
    JobRun.objects.create(
        name="expire_items", running_until=now, last_status="failed", last_error="ValueError: x",
        first_seen_at=now - timedelta(hours=1), last_success_at=now - timedelta(hours=1),
    )  # fmt: skip
    r = client_for(make_member("super_admin")).get("/api/health/jobs")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "overdue" and body["overdue"] == 1
    row = next(j for j in body["jobs"] if j["name"] == "expire_items")
    assert row["overdue"] and row["last_error"] == "ValueError: x" and row["interval_minutes"] == 5
    assert {j["name"] for j in body["jobs"]} == set(intervals)


def test_endpoint_is_not_in_the_public_api_description():
    from circuit.api import api

    assert "/api/health/jobs" not in json.dumps(api.get_openapi_schema()["paths"])


def test_all_clear(settings, make_member, client_for):
    settings.JOB_INTERVALS = {}
    body = client_for(make_member("super_admin")).get("/api/health/jobs").json()
    assert body == {"status": "ok", "overdue": 0, "jobs": []}


def test_job_health_command_prints_a_table_and_says_when_nothing_is_expected(intervals, capsys, settings):
    now = timezone.now()
    JobRun.objects.create(
        name="expire_items", running_until=now, last_status="failed", last_error="ValueError: x",
        first_seen_at=now - timedelta(hours=1), last_success_at=now - timedelta(hours=1),
    )  # fmt: skip
    call_command("job_health")
    out = capsys.readouterr().out
    assert "expire_items" in out and "OVERDUE" in out and "last error: ValueError: x" in out and "1 overdue of 3." in out
    settings.JOB_INTERVALS = {}
    call_command("job_health")
    assert "No scheduled jobs are expected here" in capsys.readouterr().out
