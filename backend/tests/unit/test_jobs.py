"""Scheduled jobs (core/jobs.py, core/management/commands/run_jobs.py) and their schedule (deploy/gcp/app.toml)."""

import json
import re
import threading
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command, get_commands, load_command_class
from django.utils import timezone

from core import flags, jobs
from core.jobs import JobCommand
from core.models import JobRun
from tests.unit.test_deploy_config import filled, gcp

pytestmark = pytest.mark.django_db


def only(settings, **audiences):
    settings.FEATURES = ",".join(f"{n}:{audiences.get(n, 'off')}" for n in flags.FLAGS)


def read(capfd):
    """Everything printed so far, split into the JSON log lines and the plain text lines (the commands' summaries)."""
    raw = capfd.readouterr().out.splitlines()
    return [json.loads(line) for line in raw if line.startswith("{")], [line for line in raw if not line.startswith("{")]


def lines(capfd):
    return read(capfd)[0]


def job_events(capfd, job):
    return [(e["event"], e) for e in lines(capfd) if e.get("job") == job]


class Recorder(JobCommand):
    """A job for testing the base class. `calls` counts how often run() really did the work."""

    job_name = "recorder"
    calls = 0
    outcome: object = {"things": 3}

    def run(self):
        type(self).calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def fresh(**attrs):
    return type("Recorder", (Recorder,), {"calls": 0, **attrs})()


# ---- the base class ----------------------------------------------------------------------------------------------------------


def test_a_job_logs_start_and_end_as_json_with_counts_and_no_names(capfd):
    job = fresh(outcome={"things": 3, "when": "2026-10-26"})
    call_command(job)
    events = job_events(capfd, "recorder")
    assert [name for name, _ in events] == ["job.start", "job.end"]
    end = events[1][1]
    assert end["things"] == 3 and isinstance(end["ms"], int) and end["severity"] == "INFO"
    assert "when" not in end  # only numbers and flags are copied into the log
    assert job.calls == 1


def test_the_job_prints_one_summary_line_and_records_its_last_run(capfd):
    call_command(fresh(outcome={"things": 3}))
    assert read(capfd)[1] == ["things=3"]
    run = JobRun.objects.get(name="recorder")
    assert run.last_status == "ok" and run.last_finished_at and run.running_until <= timezone.now()


@pytest.mark.parametrize("flag_name, command", [("daily_drop", "build_daily_drops"), ("circuits", "run_circuit_round")])
def test_a_job_whose_flag_is_off_skips_exits_cleanly_and_does_no_work(settings, monkeypatch, capfd, flag_name, command):
    only(settings)
    cmd = load_command_class(get_commands()[command], command)
    assert cmd.flag == flag_name
    monkeypatch.setattr(type(cmd), "run", lambda self: pytest.fail("the work must not run while the flag is off"))
    call_command(cmd)  # no exception = exit code 0
    events_all, plain = read(capfd)
    assert plain == ["skipped: flag off"]
    events = {e["event"]: e for e in events_all if e.get("job") == command}
    assert events["job.skipped"]["reason"] == "flag off" and "job.end" not in events
    assert not JobRun.objects.filter(name=command).exists()  # it never even asked for the lease


def test_a_job_runs_when_its_flag_is_on_for_everyone_and_for_testers_it_waits(settings):
    job = fresh(flag="circuits")
    only(settings, circuits="everyone")
    call_command(job)
    assert job.calls == 1
    only(settings, circuits="testers")  # no member = audience "everyone" only (CLAUDE.md), so a testers-only flag skips jobs
    call_command(job)
    assert job.calls == 1


def test_a_job_that_is_already_running_skips_and_exits_cleanly(capfd):
    assert jobs.acquire("recorder", 30)  # someone else holds the lease
    job = fresh()
    call_command(job)
    assert job.calls == 0
    events_all, plain = read(capfd)
    assert plain == ["skipped: already running"]
    assert {e["event"]: e for e in events_all if e.get("job") == "recorder"}["job.skipped"]["reason"] == "already running"


def test_a_failed_job_logs_the_error_type_only_frees_its_lease_and_exits_non_zero(capfd):
    job = fresh(outcome=ValueError("secret@example.com is invalid"))
    with pytest.raises(ValueError):
        call_command(job)
    failed = dict(job_events(capfd, "recorder"))["job.failed"]
    assert failed["error"] == "ValueError" and failed["severity"] == "ERROR"
    assert "secret@example.com" not in json.dumps(failed)  # the message could hold personal data
    assert JobRun.objects.get(name="recorder").last_status == "failed"
    retry = fresh()
    call_command(retry)  # the retry is not turned away by the failed run's lease
    assert retry.calls == 1


def test_a_job_that_finds_nothing_to_do_is_a_skip_not_an_end(capfd):
    call_command(
        fresh(
            outcome={"skip_reason": "not enough data", "message": "skipped: not enough data"},
            summary=lambda self, r: r["message"],
        )
    )
    events_all, plain = read(capfd)
    events = {e["event"]: e for e in events_all if e.get("job") == "recorder"}
    assert events["job.skipped"]["reason"] == "not enough data" and "job.end" not in events
    assert JobRun.objects.get(name="recorder").last_status == "skipped"
    assert plain == ["skipped: not enough data"]


def test_a_per_member_skipped_count_is_not_mistaken_for_a_skipped_job(capfd):
    # build_daily_drops reports `skipped` members as a number; only `skip_reason` skips the whole job
    call_command(fresh(outcome={"built": 5, "skipped": 2}))
    assert "job.end" in dict(job_events(capfd, "recorder"))


# ---- the lease ---------------------------------------------------------------------------------------------------------------


def test_lease_is_taken_once_released_and_expires_on_its_own():
    assert jobs.acquire("lease-test", 30) is True
    assert jobs.acquire("lease-test", 30) is False
    jobs.release("lease-test", "ok")
    assert jobs.acquire("lease-test", 30) is True
    JobRun.objects.filter(name="lease-test").update(
        running_until=timezone.now() - timedelta(seconds=1)
    )  # a killed run never released
    assert jobs.acquire("lease-test", 30) is True


def test_leases_of_different_jobs_do_not_block_each_other():
    assert jobs.acquire("one", 30) and jobs.acquire("two", 30)


@pytest.mark.django_db(transaction=True)
def test_two_runs_at_the_same_moment_do_the_work_once():
    """PRODUCTION.md §14 row 10: the scheduler retries, runs overlap, and still exactly one wins."""
    from django.db import connection

    winners, gate = [], threading.Barrier(8)

    def attempt():
        try:
            gate.wait()
            winners.append(jobs.acquire("race", 30))
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(winners) == [False] * 7 + [True]


# ---- the bundle --------------------------------------------------------------------------------------------------------------


def test_the_bundle_runs_jobs_in_order_and_each_has_its_own_log_lines(capfd):
    call_command("run_jobs", "expire_items", "send_emails")
    log_lines, plain = read(capfd)
    events = [(e["event"], e["job"]) for e in log_lines if e.get("job") and e["event"].startswith("job.")]
    assert events == [
        ("job.start", "expire_items"),
        ("job.end", "expire_items"),
        ("job.start", "send_emails"),
        ("job.end", "send_emails"),
    ]
    assert plain.index("[expire_items]") < plain.index("[send_emails]")


def test_the_bundle_skips_a_job_that_is_not_built_yet_without_failing(capfd):
    call_command("run_jobs", "expire_items", "reconcile_payments")  # arrives with B3c
    log_lines, plain = read(capfd)
    assert "[reconcile_payments] skipped: not built" in plain
    assert [e["reason"] for e in log_lines if e.get("event") == "job.skipped" and e["job"] == "reconcile_payments"] == [
        "not built"
    ]


def test_one_failing_job_does_not_stop_the_others_but_the_bundle_exits_non_zero(monkeypatch, capfd):
    from core.management.commands import expire_items

    monkeypatch.setattr(expire_items.Command, "run", lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(CommandError, match="failed: expire_items"):
        call_command("run_jobs", "expire_items", "send_emails")
    ended = [e["job"] for e in lines(capfd) if e.get("event") == "job.end"]
    assert ended == ["send_emails"]  # it ran after the failure


def test_the_bundle_refuses_a_command_that_is_not_a_job():
    with pytest.raises(CommandError, match="not a job"):
        call_command("run_jobs", "check")


def test_overlapping_bundles_do_each_job_once(settings):
    assert jobs.acquire("send_emails", 10)  # the previous bundle is still sending
    out = StringIO()
    call_command("run_jobs", "send_emails", stdout=out)
    assert "skipped: already running" in out.getvalue()


# ---- the schedule covers every job -------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prod(tmp_path_factory):
    return gcp.load_config("production", filled("production", tmp_path_factory.mktemp("cfg")))


def job_commands():
    """Every management command in the codebase that is a JobCommand."""
    found = {}
    for name, app in get_commands().items():
        if app.startswith("django.") or app in ("django_otp", "ninja"):
            continue
        if isinstance(load_command_class(app, name), JobCommand):
            found[name] = app
    return found


def test_every_job_in_the_code_has_a_cloud_run_job(prod):
    declared = {j.command for j in prod.jobs.values()}
    assert set(job_commands()) <= declared, f"add to deploy/gcp/app.toml: {set(job_commands()) - declared}"


def test_every_job_in_the_deploy_file_is_a_real_job_or_waiting_for_its_code(prod):
    for job in prod.jobs.values():
        exists = job.command in get_commands()
        if job.command == "migrate":
            continue  # Django's own command
        if job.enabled:
            assert exists, f"{job.key}: no command called {job.command}"
            assert job.command in job_commands() or job.command == "run_jobs", f"{job.command} must extend core.jobs.JobCommand"
        else:
            assert not exists, f"{job.command} now exists: switch '{job.key}' on in deploy/gcp/app.toml (enabled = true)"


CRON_FIELD = [(r"(\*|\d+)(/\d+)?", 0, 59), (r"(\*|\d+)(/\d+)?", 0, 23), (r"\*", 1, 31), (r"\*", 1, 12), (r"(\*|\d)", 0, 6)]


def test_every_enabled_job_is_scheduled_bundled_or_on_demand_and_schedules_are_valid(prod):
    for job in prod.jobs.values():
        if not job.enabled:
            continue
        assert job.schedule or job.manual or job.bundled, f"{job.key} never runs"
        if job.schedule:
            fields = job.schedule.split()
            assert len(fields) == 5, job.key
            for field, (pattern, low, high) in zip(fields, CRON_FIELD, strict=True):
                assert re.fullmatch(pattern, field), f"{job.key}: {field}"
                if field.isdigit():
                    assert low <= int(field) <= high, f"{job.key}: {field}"


def test_the_frequent_jobs_share_one_trigger_and_are_exactly_the_bundled_ones(prod):
    bundle = prod.jobs["every-5-min"]
    bundled = [j.command for j in prod.jobs.values() if j.bundled]
    assert sorted(bundle.args) == sorted(bundled)
    assert all(not j.schedule for j in prod.jobs.values() if j.bundled)  # a bundled job with its own trigger would run twice
    assert bundle.command == "run_jobs" and bundle.schedule == "*/5 * * * *"


def test_every_job_named_in_the_engineering_guide_is_scheduled(prod):
    required = {
        "compute_matches", "build_daily_drops", "build_investor_picks", "reconcile_payments", "run_circuit_round",
        "retention_cleanup", "train_ranker", "expire_items", "send_emails", "build_exports", "delete_accounts",
    }  # fmt: skip
    in_file = {j.command for j in prod.jobs.values()}
    assert required <= in_file
    runs_somewhere = {j.command for j in prod.jobs.values() if j.schedule or j.bundled} | set(prod.jobs["every-5-min"].args)
    assert required <= runs_somewhere


def test_daily_drop_and_investor_picks_run_at_0800_india_time_after_matches(prod):
    assert prod.jobs["build-daily-drops"].schedule == "0 8 * * *"
    assert prod.jobs["build-investor-picks"].schedule == "0 8 * * *"
    assert prod.jobs["compute-matches"].schedule == "30 7 * * *"  # finishes before the drop
    assert prod.jobs["reconcile-payments"].schedule == "*/10 * * * *"


def test_demo_reset_exists_only_in_demo(tmp_path):
    names = {
        env: {j.key for j in gcp.load_config(env, filled(env, tmp_path / env)).active_jobs()}
        for env in ("production", "staging", "demo")
    }
    assert "reset-demo" in names["demo"]
    assert "reset-demo" not in names["production"] | names["staging"]


def test_the_deploy_plan_creates_one_trigger_for_every_scheduled_job_and_none_for_the_rest(prod):
    steps = gcp.plan_deploy(prod, "abc", gcp.DeployState("1"))
    triggers = {s.argv[5] for s in steps if s.argv[:5] == ["gcloud", "scheduler", "jobs", "create", "http"]}
    expected = {prod.job_name(j.key) for j in prod.active_jobs() if j.schedule}
    assert triggers == expected
    assert prod.job_name("every-5-min") in triggers and prod.job_name("send-emails") not in triggers
