"""Monitoring as code (infra/monitoring/*.json + scripts/gcp_monitoring.py + `gcp.py monitoring`). No Google account: HTTP is faked."""

import json

import pytest

from tests.unit.test_deploy_config import ENVS, REPO, filled, gcp

mon = gcp.gcp_monitoring
TEMPLATES = sorted((REPO / "infra" / "monitoring").glob("*.json"))
VALUES = {
    "PROJECT": "circuit-test-1",
    "ENV": "production",
    "SERVICE": "circuit-production-api",
    "API_HOST": "api.circuit.example",
    "APP_HOST": "app.circuit.example",
    "LANDING_HOST": "circuit.example",
    "CHANNELS": json.dumps(["channel:Circuit on-call email", "channel:Circuit on-call phone"]),
}


@pytest.fixture(params=ENVS)
def cfg(request, tmp_path):
    return gcp.load_config(request.param, filled(request.param, tmp_path))


@pytest.fixture
def prod(tmp_path):
    return gcp.load_config("production", filled("production", tmp_path))


def rendered():
    return {name: json.loads(text) for name, text in mon.render(VALUES).items()}


def test_every_template_renders_to_valid_json_with_no_placeholder_left():
    out = mon.render(VALUES)
    assert len(out) == len(TEMPLATES) >= 14
    for name, text in out.items():
        assert "${" not in text, name
        assert json.loads(text)["kind"] in mon.KINDS


def test_the_alerts_the_prompt_asks_for_exist():
    names = {b["displayName"] for b in rendered().values() if b["kind"] == "alertPolicy"}
    text = " ".join(names)
    for word in ("down", "5xx", "slow", "failed", "overdue", "watcher", "free-tier"):
        assert word in text, word
    kinds = [b["kind"] for b in rendered().values()]
    assert kinds.count("uptimeCheck") == 3


def test_thresholds_match_production_md():
    r = rendered()
    latency = r["alert-latency.json"]["conditions"][0]["conditionThreshold"]
    assert latency["thresholdValue"] == 1000 and latency["duration"] == "600s"  # PRODUCTION.md §8: p95 > 1 s for 10 minutes
    fivexx = r["alert-5xx.json"]["conditions"][0]["conditionThreshold"]
    assert fivexx["thresholdValue"] == 0.02 and fivexx["duration"] == "300s"
    heartbeat = r["alert-jobs-heartbeat.json"]["conditions"][0]["conditionAbsent"]
    assert heartbeat["duration"] == "1800s"


def test_every_alert_reaches_the_channels():
    for name, body in rendered().items():
        if body["kind"] == "alertPolicy":
            assert body["notificationChannels"] == ["channel:Circuit on-call email", "channel:Circuit on-call phone"], name


def test_log_metrics_match_the_events_the_code_logs():
    filters = " ".join(b["filter"] for b in rendered().values() if b["kind"] == "logMetric")
    for event in ("job.failed", "job.overdue", "usage.warning", "job.end"):
        assert f'jsonPayload.event="{event}"' in filters, event
    root = REPO / "backend"
    sources = "\n".join(p.read_text() for p in (root / "core").rglob("*.py"))
    assert '"job.failed"' in sources and '"job.end"' in sources  # the strings the filters depend on


def test_metric_names_are_per_environment_so_environments_can_share_a_project():
    names = [b["name"] for b in rendered().values() if b["kind"] == "logMetric"]
    assert all(n.startswith("circuit_production_") for n in names)


def test_missing_variable_or_channels_stop_early():
    with pytest.raises(mon.MonitoringError):
        mon.variables(
            project="p",
            env="production",
            service="s",
            api_url="https://a.example",
            app_url="https://b.example",
            landing_url="https://c.example",
            channels=[],
        )
    with pytest.raises(mon.MonitoringError):
        mon.variables(
            project="p",
            env="production",
            service="s",
            api_url="auto",
            app_url="https://b.example",
            landing_url="https://c.example",
            channels=["x"],
        )
    assert mon.host_of("https://app.circuit.example/path?x=1") == "app.circuit.example"


# ---- apply, against a fake Google ------------------------------------------------------------------------------------------


class FakeGoogle:
    def __init__(self, channels=("Circuit on-call email", "Circuit on-call phone"), existing=None):
        self.calls: list[tuple[str, str]] = []
        self.channels = list(channels)
        self.existing = existing or {}  # list url fragment -> items

    def __call__(self, method, url, token, body=None):
        assert token == "tok"
        self.calls.append((method, url.split("?")[0].split("/v3/")[-1].split("/v2/")[-1]))
        if method == "GET":
            if "notificationChannels" in url:
                return 200, {
                    "notificationChannels": [
                        {"displayName": c, "name": f"projects/p/notificationChannels/{i}"} for i, c in enumerate(self.channels)
                    ]
                }
            for key, items in self.existing.items():
                if url.split("?")[0].endswith("/" + key):
                    return 200, {key: items}
            return 200, {}
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            self.last_body = body
            return 200, {}
        raise AssertionError(method)


def test_apply_creates_everything_on_an_empty_project_and_resolves_channels():
    google = FakeGoogle()
    lines = mon.apply(mon.render(VALUES), "p", http=google, token="tok", out=lambda _: None)
    assert len(lines) == len(TEMPLATES) and all(line.startswith("created") for line in lines)
    posts = [c for c in google.calls if c[0] == "POST"]
    assert [p[1] for p in posts][:4] == ["projects/p/metrics"] * 4  # metrics first: the alert policies read them
    assert not any(c[0] in ("PUT", "PATCH", "DELETE") for c in google.calls)


def test_apply_twice_updates_instead_of_duplicating():
    existing = {
        "metrics": [{"name": "circuit_production_job_failed"}],
        "alertPolicies": [{"displayName": "Circuit production: API slow (p95 above 1 s)", "name": "projects/p/alertPolicies/9"}],
    }
    google = FakeGoogle(existing=existing)
    lines = mon.apply(mon.render(VALUES), "p", http=google, token="tok", out=lambda _: None)
    assert any(line.startswith("updated") and "job_failed" in line for line in lines)
    assert ("PATCH", "projects/p/alertPolicies/9") in google.calls
    assert sum(1 for c in google.calls if c == ("POST", "projects/p/alertPolicies")) == 6  # the other six policies are new


def test_a_moved_host_replaces_the_uptime_check():
    old = {
        "displayName": "Circuit production API /ready",
        "name": "projects/p/uptimeCheckConfigs/5",
        "monitoredResource": {"type": "uptime_url", "labels": {"project_id": "p", "host": "old.run.app"}},
    }
    google = FakeGoogle(existing={"uptimeCheckConfigs": [old]})
    lines = mon.apply(mon.render(VALUES), "p", http=google, token="tok", out=lambda _: None)
    assert any(line.startswith("replaced") for line in lines)
    assert ("DELETE", "projects/p/uptimeCheckConfigs/5") in google.calls


def test_unknown_channel_stops_before_anything_changes():
    google = FakeGoogle(channels=["Someone else"])
    with pytest.raises(mon.MonitoringError, match="Circuit on-call email"):
        mon.apply(mon.render(VALUES), "p", http=google, token="tok", out=lambda _: None)
    assert not any(c[0] != "GET" for c in google.calls)


def test_a_google_error_is_reported_with_its_message():
    def failing(method, url, token, body=None):
        return (403, {"error": {"message": "Permission denied"}}) if method != "GET" else (200, {})

    def channels_ok(method, url, token, body=None):
        if "notificationChannels" in url:
            return 200, {
                "notificationChannels": [
                    {"displayName": n, "name": f"c/{n}"} for n in ("Circuit on-call email", "Circuit on-call phone")
                ]
            }
        return failing(method, url, token, body)

    with pytest.raises(mon.MonitoringError, match="403: Permission denied"):
        mon.apply(mon.render(VALUES), "p", http=channels_ok, token="tok", out=lambda _: None)


# ---- the gcp.py command -----------------------------------------------------------------------------------------------------


def test_plan_monitoring_writes_every_file_and_names_them(prod):
    prod.monitoring["notification_channels"] = ["Circuit on-call email", "Circuit on-call phone"]
    steps = gcp.plan_monitoring(prod, "123456789")
    assert steps[0].argv[:4] == ["gcloud", "services", "enable", "monitoring.googleapis.com"]
    apply_step = steps[1]
    assert apply_step.local and apply_step.changes
    written = {p.name for p in apply_step.files}
    assert written == {p.name for p in TEMPLATES}
    assert set(apply_step.argv[apply_step.argv.index("--files") + 1 :]) == written
    api_host = "circuit-production-api-123456789.asia-south1.run.app"
    assert any(api_host in text for text in apply_step.files.values())  # API_URL=auto resolved with the project number


def test_monitoring_with_no_channels_stops_with_a_message_not_a_traceback():
    out: list[str] = []
    assert gcp.main(["monitoring", "--env", "production"], out=out.append) == 1
    assert "No notification channels" in "\n".join(out)


def test_a_placeholder_channel_blocks_a_real_monitoring_run(prod, monkeypatch):
    prod.monitoring["notification_channels"] = ["<Circuit production on-call email>"]
    monkeypatch.setattr(gcp, "load_config", lambda env: prod)
    out: list[str] = []
    assert gcp.main(["monitoring", "--env", "production"], out=out.append) == 1
    assert "notification_channels" in "\n".join(out)


def test_staging_and_demo_declare_channels_production_may_leave_them_empty(cfg):
    if cfg.env != "production":
        assert len(cfg.monitoring["notification_channels"]) >= 2
    else:
        assert cfg.monitoring["notification_channels"] == []  # beta week 1: no alerts yet


def test_apply_script_rejects_a_file_that_is_not_there(tmp_path, capsys):
    assert mon.main(["apply", "--project", "p", "--dir", str(tmp_path), "--files", "nope.json"]) == 1
    assert "nope.json" in capsys.readouterr().out
