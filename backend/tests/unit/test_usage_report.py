"""The weekly free-tier usage report: what it measures, when it warns, and that it never fails because one reading is unavailable."""

import json

import pytest
from django.core.management import call_command
from django.utils import timezone

from core import usage, usage_report
from core.models import JobRun, OutboundEmail

pytestmark = pytest.mark.django_db


def by_key(readings):
    return {r.key: r for r in readings}


@pytest.fixture
def small_limits(settings):
    settings.FREE_TIER_LIMITS = {**settings.FREE_TIER_LIMITS, "emails_month": 10, "emails_day": 5, "auth_users": 4}


def test_a_reading_warns_at_70_percent_and_not_before(settings):
    settings.USAGE_WARN_PCT = 70
    r = usage_report.Reading("x", "X", 69, 100, "")
    assert r.pct == 69 and not r.warn
    assert usage_report.Reading("x", "X", 70, 100, "").warn
    assert not usage_report.Reading("x", "X", 5, None, "").warn  # nothing to compare against (no limit): never a warning
    assert not usage_report.Reading("x", "X", None, 100, "").warn  # not measurable


def test_the_database_size_is_measured():
    r = usage_report.database_size()
    assert r.used > 1_000_000 and r.limit == 500 * 1024**2 and 0 <= r.pct < 100


def test_storage_is_n_a_where_there_is_no_supabase_storage_schema():
    r = usage_report.storage_size()
    assert r.used is None and "n/a" in r.text()


def test_emails_this_month_and_the_busiest_day(small_limits, make_member):
    now = timezone.now()
    for _ in range(4):
        OutboundEmail.objects.create(
            to_email="a@example.org", kind="x", subject="s", body="b", status="sent", sent_at=now, next_attempt_at=now
        )
    month, busiest = usage_report.emails()
    assert month.used == 4 and month.pct == 40 and busiest.used == 4 and busiest.pct == 80 and busiest.warn


def test_sign_in_accounts_count_real_members_only(make_member, small_limits):
    make_member("student")
    make_member("founder")
    make_member("student", is_simulated=True)
    make_member("student", deleted_at=timezone.now())
    r = usage_report.sign_in_accounts()
    assert r.used == 2 and r.pct == 50


def test_redis_readings_come_from_info():
    memory, commands = usage_report.redis_readings()
    assert memory.key == "redis_memory_bytes" and commands.key == "redis_commands_month"
    assert memory.limit == 256 * 1024**2 and commands.limit == 500_000


def test_redis_down_is_n_a_not_an_error(monkeypatch):
    class Dead:
        client = type("C", (), {"info": staticmethod(lambda: (_ for _ in ()).throw(ConnectionError("down")))})()

    monkeypatch.setattr("core.cache.get_cache", lambda: Dead())
    memory, commands = usage_report.redis_readings()
    assert memory.used is None and commands.used is None and "ConnectionError" in memory.text()


def test_ai_calls_are_compared_with_the_daily_cap(settings):
    settings.LLM_DAILY_CALL_LIMIT = 10
    usage.bump("llm_calls", 8)
    (r,) = usage_report.llm_readings()
    assert r.used == 8 and r.pct == 80 and r.warn
    settings.LLM_DAILY_CALL_LIMIT = 0
    (r,) = usage_report.llm_readings()
    assert r.pct is None and "no daily cap" in r.note


def test_one_broken_measurement_does_not_hide_the_others(monkeypatch):
    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(usage_report, "database_size", broken)
    keys = by_key(usage_report.collect())
    assert "database_bytes" not in keys and "emails_month" in keys


def test_run_logs_a_warning_for_each_reading_at_the_threshold_and_a_summary(small_limits, make_member, capfd, settings):
    for _ in range(3):
        make_member("student")
    capfd.readouterr()
    readings, counts = usage_report.run()
    lines = [json.loads(line) for line in capfd.readouterr().out.splitlines() if line.startswith("{")]
    warnings = [line for line in lines if line.get("event") == "usage.warning"]
    assert {w["what"] for w in warnings} == {r.key for r in readings if r.warn} and warnings
    assert all(w["severity"] == "WARNING" and isinstance(w["percent"], int) for w in warnings)
    assert counts == {"checked": len(readings), "warnings": len(warnings)}
    report = next(line for line in lines if line.get("event") == "usage.report")
    assert isinstance(report["database_bytes"], int)


def test_logs_contain_numbers_and_names_of_limits_only(small_limits, make_member, capfd):
    make_member("student", email="private.person@example.org", display_name="Private Person")
    capfd.readouterr()
    usage_report.run()
    out = capfd.readouterr().out
    assert "private.person" not in out and "Private Person" not in out


def test_the_command_prints_a_table_and_is_a_job(small_limits, capsys):
    call_command("usage_report")
    out = capsys.readouterr().out
    assert "Database size" in out and "Emails sent this month" in out and "AI calls today" in out and "Not measured here" in out
    row = JobRun.objects.get(name="usage_report")
    assert row.last_status == "ok" and row.last_success_at


def test_the_table_marks_the_warnings(small_limits, make_member, capsys):
    for _ in range(4):
        make_member("student")
    call_command("usage_report")
    lines = capsys.readouterr().out.splitlines()
    marked = [line for line in lines if line.startswith("!!")]
    assert any("Sign-in accounts" in line and "100%" in line for line in marked)


def test_a_paid_plan_raises_the_limits_from_the_environment():
    from tests.unit.test_config import make

    config = make(free_tier_limits='{"database_bytes": 8589934592}')
    assert config.free_tier_limit_overrides() == {"database_bytes": 8589934592}
    for bad in ("not json", "[1]", '{"database_bytes": "big"}', '{"database_bytes": -1}'):
        with pytest.raises(ValueError):
            make(free_tier_limits=bad)


def test_the_report_is_scheduled_weekly_and_the_alert_reads_its_warnings():
    import tempfile
    from pathlib import Path

    from tests.unit.test_deploy_config import REPO, filled, gcp

    with tempfile.TemporaryDirectory() as tmp:
        cfg = gcp.load_config("production", filled("production", Path(tmp)))
    assert cfg.jobs["usage-report"].schedule == "0 9 * * 1" and gcp.job_intervals(cfg)["usage_report"] == 10080
    assert "usage.warning" in (REPO / "infra/monitoring/metric-usage-warning.json").read_text()
