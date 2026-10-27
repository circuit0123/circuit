"""The deploy plan (scripts/gcp.py + deploy/gcp/*.toml). No gcloud and no cloud account: plans are plain data, and the runner is
replaced by a recording fake."""

import importlib.util
import re
import shutil
import subprocess
import sys

import pytest
import yaml
from django.conf import settings

REPO = settings.BASE_DIR.parent


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, REPO / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


gcp = _load("gcp", "scripts/gcp.py")
ENVS = list(gcp.ENVS)
STATE = gcp.DeployState(project_number="123456789", serving_revision=None)
LATER = gcp.DeployState(project_number="123456789", serving_revision="circuit-production-api-00007-abc")


def filled(env: str, tmp_path):
    """The committed config with every <placeholder> replaced by a plausible value, as the deployer would."""
    shutil.copytree(REPO / "deploy" / "gcp", tmp_path / env, ignore=shutil.ignore_patterns(".rendered"))
    for toml in (tmp_path / env).glob("*.toml"):
        text = toml.read_text()
        text = text.replace("<your-gcp-project-id>", "circuit-test-1").replace("<XXXXXX-XXXXXX-XXXXXX>", "AAAAAA-BBBBBB-CCCCCC")
        text = text.replace("<pick-a-random-path>", "k3j9x2m8q1").replace(
            "<https://xxxx.supabase.co>", "https://abcd.supabase.co"
        )
        text = text.replace("Circuit <hello@<yourdomain>>", "Circuit <hello@circuit.example>")
        text = re.sub(r"<(https://[^>]+)>", r"\1", text)
        text = re.sub(r"<([a-z]+@[^>]+)>", r"\1", text)
        text = re.sub(r"<(Circuit [a-z]+ on-call [a-z]+)>", r"\1", text)
        text = text.replace("<age1...>", "age1" + "q" * 58)
        # production.toml now holds the real project and billing account; the tests use their own so they do not depend on them
        text = re.sub(r'(?m)^id\s*=\s*"[^"]*"', 'id = "circuit-test-1"', text)
        text = re.sub(r'(?m)^billing_account\s*=\s*"[^"]*"', 'billing_account = "AAAAAA-BBBBBB-CCCCCC"', text)
        text = text.replace("<name>", "Asha Rao").replace("<postal address>", "1 Example Road, Chennai")
        toml.write_text(text)
    return tmp_path / env


@pytest.fixture(params=ENVS)
def cfg(request, tmp_path):
    return gcp.load_config(request.param, filled(request.param, tmp_path))


@pytest.fixture
def prod(tmp_path):
    return gcp.load_config("production", filled("production", tmp_path))


def all_argv(steps):
    return [" ".join(s.argv) for s in steps]


# ---- the committed files ------------------------------------------------------------------------------------------------


def test_every_environment_file_loads_and_names_are_valid_for_google_cloud(cfg):
    assert not gcp.find_placeholders(cfg)
    assert re.fullmatch(r"[a-z][a-z0-9-]{0,62}", cfg.service_name)
    for job in cfg.active_jobs():
        assert re.fullmatch(r"[a-z][a-z0-9-]{0,62}", cfg.job_name(job.key)), job.key
    for name in cfg.secrets:
        assert re.fullmatch(r"[A-Za-z0-9_-]{1,255}", cfg.secret_id(name))
    for sa in (cfg.runtime_sa, cfg.scheduler_sa):
        assert 6 <= len(sa.split("@")[0]) <= 30  # service account ids


def test_a_config_with_placeholders_left_is_refused_before_anything_runs(monkeypatch, tmp_path):
    folder = filled("production", tmp_path)
    toml = folder / "production.toml"
    toml.write_text(toml.read_text().replace("circuit-test-1", "<your-gcp-project-id>"))  # as in a freshly cloned repo
    monkeypatch.setattr(gcp, "DEPLOY_DIR", folder)
    assert any("project.id" in item for item in gcp.find_placeholders(gcp.load_config("production")))
    out: list[str] = []
    assert gcp.main(["setup", "--env", "production"], input_fn=lambda _: pytest.fail("must not ask"), out=out.append) == 1
    assert any("fill in" in line for line in out)


def test_unknown_environment_is_rejected():
    with pytest.raises(gcp.DeployError):
        gcp.load_config("prod")


def test_production_defaults_cost_nothing_while_idle_and_stay_small(prod):
    assert prod.service["min_instances"] == 0
    assert prod.service["max_instances"] <= 3


def test_service_concurrency_matches_gunicorn_workers_times_threads(prod):
    spec = importlib.util.spec_from_file_location("gunicorn_conf", REPO / "backend/circuit/gunicorn.py")
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
    assert prod.service["concurrency"] == conf.workers * conf.threads
    assert prod.service["timeout_seconds"] == conf.timeout


def test_probes_never_depend_on_the_database(prod):
    # /ready checks Postgres: using it for liveness would restart healthy instances in a loop during a Supabase outage.
    assert prod.service["startup_probe_path"] == "/health"
    assert prod.service["liveness_probe_path"] == "/health"


# ---- YAML writer ----------------------------------------------------------------------------------------------------------


def test_yaml_writer_round_trips_through_a_real_yaml_parser(cfg):
    manifests = [
        gcp.service_manifest(cfg, cfg.image("abc"), "1", None),
        gcp.service_manifest(cfg, cfg.image("abc"), "1", "rev-1"),
        *[gcp.job_manifest(cfg, j, cfg.image("abc"), "1") for j in cfg.active_jobs()],
    ]
    for manifest in manifests:
        assert yaml.safe_load(gcp.yaml_dump(manifest)) == manifest


def test_yaml_writer_keeps_numbers_like_strings_as_strings():
    assert yaml.safe_load(gcp.yaml_dump({"a": "0", "b": "true", "c": 5, "d": True, "e": [], "f": {}})) == {
        "a": "0",
        "b": "true",
        "c": 5,
        "d": True,
        "e": [],
        "f": {},
    }


# ---- manifests ------------------------------------------------------------------------------------------------------------


def test_service_manifest_mounts_every_secret_by_reference_and_never_holds_a_value(cfg):
    manifest = gcp.service_manifest(cfg, cfg.image("abc"), "1", None)
    env = manifest["spec"]["template"]["spec"]["containers"][0]["env"]
    refs = {e["name"]: e["valueFrom"]["secretKeyRef"] for e in env if "valueFrom" in e}
    assert set(refs) == set(cfg.secrets)
    for name, ref in refs.items():
        assert ref == {"name": cfg.secret_id(name), "key": "latest"}
    plain = {e["name"] for e in env if "value" in e}
    assert not plain & set(cfg.secrets)  # a secret is never also a plain value
    assert "PORT" not in plain  # Cloud Run sets it itself


def test_api_url_auto_becomes_the_services_own_address(prod):
    env = {e["name"]: e.get("value") for e in gcp.container_env(prod, "123456789")}
    assert env["API_URL"] == "https://circuit-production-api-123456789.asia-south1.run.app"


def test_first_deploy_sends_all_traffic_to_the_new_revision_later_deploys_start_at_zero(prod):
    first = gcp.service_manifest(prod, prod.image("a"), "1", None)["spec"]["traffic"]
    assert first == [{"latestRevision": True, "percent": 100}]
    later = gcp.service_manifest(prod, prod.image("a"), "1", "rev-7")["spec"]["traffic"]
    assert later == [{"revisionName": "rev-7", "percent": 100}, {"latestRevision": True, "percent": 0, "tag": "next"}]


def test_jobs_run_the_same_image_with_their_own_command_and_the_runtime_account(prod):
    job = prod.find_job("compute_matches")
    spec = gcp.job_manifest(prod, job, prod.image("a"), "1")["spec"]["template"]["spec"]["template"]["spec"]
    assert spec["containers"][0]["command"] == ["python", "manage.py", "compute_matches"]
    assert spec["serviceAccountName"] == prod.runtime_sa
    assert spec["containers"][0]["image"] == prod.image("a")


def test_migrate_job_is_never_retried(prod):
    spec = gcp.job_manifest(prod, prod.find_job("migrate"), prod.image("a"), "1")["spec"]["template"]["spec"]["template"]["spec"]
    assert spec["maxRetries"] == 0


# ---- setup plan ----------------------------------------------------------------------------------------------------------


def test_setup_creates_every_secret_and_lets_only_the_runtime_account_read_it(prod):
    lines = all_argv(gcp.plan_setup(prod))
    for name in prod.secrets:
        sid = prod.secret_id(name)
        assert any(f"secrets create {sid} " in line and "--locations=asia-south1" in line for line in lines)
        assert any(
            f"secrets add-iam-policy-binding {sid} " in line
            and f"serviceAccount:{prod.runtime_sa}" in line
            and "roles/secretmanager.secretAccessor" in line
            for line in lines
        )


def test_setup_grants_project_wide_roles_only_to_the_deploy_account_and_only_the_listed_ones(prod):
    for line in all_argv(gcp.plan_setup(prod)) + all_argv(gcp.plan_deploy(prod, "abc", STATE)):
        if line.startswith("gcloud projects add-iam-policy-binding"):
            assert f"--member=serviceAccount:{prod.deploy_sa}" in line, (
                "the runtime and scheduler accounts get nothing project-wide"
            )
            assert any(f"--role={role}" in line for role in gcp.DEPLOY_ROLES)
    assert not {"roles/owner", "roles/editor", "roles/iam.securityAdmin", "roles/secretmanager.secretAccessor"} & set(
        gcp.DEPLOY_ROLES
    )


def test_setup_budget_alerts_at_50_80_100_and_counts_usage_before_credits(prod):
    (budget,) = [s for s in gcp.plan_setup(prod) if s.argv[:4] == ["gcloud", "billing", "budgets", "create"]]
    line = " ".join(budget.argv)
    for pct in ("0.5", "0.8", "1.0"):
        assert f"--threshold-rule=percent={pct}" in line
    assert "--credit-types-treatment=exclude-all-credits" in line  # otherwise free credits keep the net cost at zero
    assert f"--budget-amount={prod.budget}" in line and "--billing-account=AAAAAA-BBBBBB-CCCCCC" in line


def test_setup_steps_are_safe_to_rerun(prod):
    for step in gcp.plan_setup(prod):
        creates = step.argv[:4] in (
            ["gcloud", "secrets", "create", step.argv[3]],
            ["gcloud", "iam", "service-accounts", "create"],
        ) or step.argv[3:5] == ["repositories", "create"]
        if creates or step.argv[:4] == ["gcloud", "billing", "budgets", "create"]:
            assert step.skip_if, f"{step.argv[:4]} would fail on the second run"


# ---- deploy plan ---------------------------------------------------------------------------------------------------------


def index_of(steps, needle):
    return next(i for i, s in enumerate(steps) if needle in " ".join(s.argv))


def test_deploy_checks_secrets_then_builds_then_migrates_then_deploys_in_that_order(prod):
    steps = gcp.plan_deploy(prod, "abc123", LATER)
    order = [
        index_of(steps, "secrets versions list"),
        index_of(steps, "docker buildx build"),
        index_of(steps, "jobs execute circuit-production-migrate"),
        index_of(steps, "services replace"),
        index_of(steps, "update-traffic"),
    ]
    assert order == sorted(order)
    migrate = steps[order[2]]
    assert "--wait" in migrate.argv  # the run must finish before the new revision is created


def test_deploy_requires_a_value_in_every_secret_before_building(prod):
    checks = [s for s in gcp.plan_deploy(prod, "abc", STATE) if s.must_have_output]
    assert len(checks) == len(prod.secrets)
    assert all(not s.changes for s in checks)


def test_deploy_builds_a_cloud_run_image_tagged_with_the_commit(prod):
    build = next(s for s in gcp.plan_deploy(prod, "abc123", STATE) if s.argv[:3] == ["docker", "buildx", "build"])
    assert "linux/amd64" in build.argv and "--push" in build.argv
    assert prod.image("abc123") in build.argv


def test_later_deploys_test_the_new_revision_before_it_gets_traffic(prod):
    steps = gcp.plan_deploy(prod, "abc", LATER, ["https://app.example"])
    smoke_next = next(i for i, s in enumerate(steps) if "next---" in " ".join(s.argv))
    shift = index_of(steps, "--to-latest")
    live_smoke = next(i for i, s in enumerate(steps) if i > shift and "smoke.py" in " ".join(s.argv))
    assert smoke_next < shift < live_smoke
    assert "--origin" in steps[smoke_next].argv and "https://app.example" in steps[smoke_next].argv


def test_first_deploy_has_no_test_address_step(prod):
    assert not any("next---" in line for line in all_argv(gcp.plan_deploy(prod, "abc", STATE)))


def test_deploy_creates_a_job_and_a_trigger_for_every_scheduled_job(prod):
    lines = all_argv(gcp.plan_deploy(prod, "abc", STATE))
    for job in prod.active_jobs():
        assert any("jobs replace" in line and f"job-{job.key}.yaml" in line for line in lines), job.key
        if job.schedule:
            assert any(
                f"scheduler jobs create http {prod.job_name(job.key)} " in line and f"--schedule={job.schedule}" in line
                for line in lines
            )
            assert any(f"run jobs add-iam-policy-binding {prod.job_name(job.key)} " in line for line in lines)


def test_schedules_run_in_india_time_and_the_scheduler_account_can_only_start_jobs(prod):
    triggers = [s for s in gcp.plan_deploy(prod, "abc", STATE) if s.argv[:5] == ["gcloud", "scheduler", "jobs", "create", "http"]]
    assert triggers
    for step in triggers:
        assert "--time-zone=Asia/Kolkata" in step.argv
        assert f"--oauth-service-account-email={prod.scheduler_sa}" in step.argv
        update_argv = step.use_if_exists[1]  # a rerun updates the trigger instead of failing
        assert update_argv[:5] == ["gcloud", "scheduler", "jobs", "update", "http"]


def test_every_file_a_step_writes_lives_under_the_rendered_folder(prod):
    for step in gcp.plan_deploy(prod, "abc", STATE) + gcp.plan_setup(prod):
        for path in step.files:
            assert gcp.RENDERED in path.parents
    assert "deploy/gcp/.rendered/" in (REPO / ".gitignore").read_text()


# ---- secret, rollback, jobs-run, logs ------------------------------------------------------------------------------------


def test_secret_value_never_appears_in_the_command_and_comes_from_a_hidden_prompt(prod):
    (step,) = gcp.plan_secret(prod, "secret_key")
    assert step.stdin_prompt and "--data-file=-" in step.argv
    assert all("=" not in a or a.startswith("--") for a in step.argv)


def test_secret_rejects_a_name_that_is_not_one_of_the_environments_secrets(prod):
    with pytest.raises(gcp.DeployError):
        gcp.plan_secret(prod, "RAZORPAY_KEY_SECRET")


REVS = [gcp.Revision(f"r{n}", f"img:{n}") for n in (9, 8, 7)]


def test_rollback_picks_the_revision_before_the_one_serving():
    assert gcp.choose_rollback(REVS, "r9", None).name == "r8"
    assert gcp.choose_rollback(REVS, "r8", None).name == "r7"


def test_rollback_to_a_named_revision_and_its_refusals():
    assert gcp.choose_rollback(REVS, "r9", "r7").image == "img:7"
    for serving, target in [("r7", None), ("r9", "r9"), ("r9", "nope"), ("zzz", None)]:
        with pytest.raises(gcp.DeployError):
            gcp.choose_rollback(REVS, serving, target)


def test_rollback_moves_traffic_and_every_job_to_the_older_image(prod):
    steps = gcp.plan_rollback(prod, gcp.Revision("r8", "img:8"), STATE)
    assert "--to-revisions=r8=100" in steps[0].argv
    updated = [s for s in steps if s.argv[:4] == ["gcloud", "run", "jobs", "update"]]
    assert {s.argv[4] for s in updated} == {prod.job_name(j.key) for j in prod.active_jobs()}
    assert all("--image=img:8" in s.argv for s in updated)


def test_jobs_run_accepts_either_spelling_and_refuses_unknown_or_disabled_jobs(prod):
    for name in ("compute_matches", "compute-matches"):
        (step,) = gcp.plan_jobs_run(prod, name)
        assert (
            step.argv[:5] == ["gcloud", "run", "jobs", "execute", "circuit-production-compute-matches"] and "--wait" in step.argv
        )
    for bad in ("nope", "reconcile_payments", "reset_demo"):  # not built yet / demo only
        with pytest.raises(gcp.DeployError):
            gcp.plan_jobs_run(prod, bad)


def test_logs_only_read(prod):
    for job in (None, "compute_matches"):
        (step,) = gcp.plan_logs(prod, job, 20)
        assert not step.changes


# ---- running a plan ------------------------------------------------------------------------------------------------------


class FakeRun:
    """Stands in for subprocess.run: records every call and answers from a script."""

    def __init__(self, fail_on: str | None = None, silent_probes: bool = False):
        self.calls: list[tuple[list[str], str | None]] = []
        self.cwds: list = []
        self.fail_on, self.silent_probes = fail_on, silent_probes

    def __call__(self, argv, input=None, capture_output=False, text=False, cwd=None):
        self.calls.append((list(argv), input))
        self.cwds.append(cwd)
        failing = self.fail_on is not None and self.fail_on in " ".join(argv)
        out = "" if self.silent_probes else "something"
        return subprocess.CompletedProcess(argv, 1 if failing else 0, stdout=out, stderr="boom" if failing else "")


def test_run_plan_stops_at_the_first_failure_and_runs_nothing_after_it(prod):
    run = FakeRun(fail_on="jobs execute")
    with pytest.raises(gcp.DeployError, match="Step"):
        gcp.run_plan(gcp.plan_deploy(prod, "abc", STATE), run, out=lambda *_: None)
    ran = [" ".join(c[0]) for c in run.calls]
    assert any("jobs execute" in r for r in ran)
    assert not any("services replace" in r for r in ran)  # the new revision never exists if migrations fail


def test_run_plan_skips_what_already_exists_and_runs_what_is_missing(prod):
    present = FakeRun()  # every "describe" probe prints something: it exists
    gcp.run_plan(gcp.plan_setup(prod), present, out=lambda *_: None)
    assert not any("secrets create" in " ".join(c[0]) for c in present.calls)
    absent = FakeRun(silent_probes=True)  # probes print nothing: it does not exist
    gcp.run_plan(gcp.plan_setup(prod), absent, out=lambda *_: None)
    assert any("secrets create" in " ".join(c[0]) for c in absent.calls)


def test_run_plan_updates_a_trigger_that_exists_and_creates_one_that_does_not(prod):
    steps = [s for s in gcp.plan_deploy(prod, "abc", STATE) if s.use_if_exists][:1]
    exists = FakeRun()
    gcp.run_plan(steps, exists, out=lambda *_: None)
    assert exists.calls[-1][0][3:5] == ["update", "http"]
    missing = FakeRun(fail_on="scheduler jobs describe")
    gcp.run_plan(steps, missing, out=lambda *_: None)
    assert missing.calls[-1][0][3:5] == ["create", "http"]


def test_run_plan_refuses_to_deploy_when_a_secret_is_empty(prod):
    with pytest.raises(gcp.DeployError, match="make secret"):
        gcp.run_plan(gcp.plan_deploy(prod, "abc", STATE)[:1], FakeRun(silent_probes=True), out=lambda *_: None)


def test_run_plan_sends_the_secret_value_on_standard_input_only(prod):
    run = FakeRun()
    gcp.run_plan(gcp.plan_secret(prod, "SECRET_KEY"), run, ask_secret=lambda _: "s3cr3t-value", out=lambda *_: None)
    argv, stdin = run.calls[-1]
    assert stdin == "s3cr3t-value" and not any("s3cr3t" in a for a in argv)


def test_run_plan_never_echoes_the_secret_value(prod):
    lines: list[str] = []
    gcp.run_plan(gcp.plan_secret(prod, "SECRET_KEY"), FakeRun(), ask_secret=lambda _: "s3cr3t-value", out=lines.append)
    assert not any("s3cr3t" in line for line in lines)


def test_run_plan_an_optional_step_may_fail(prod):
    steps = [s for s in gcp.plan_setup(prod) if s.optional]
    assert steps
    gcp.run_plan(steps, FakeRun(fail_on="set-cleanup-policies"), out=lambda *_: None)  # no exception


# ---- the command line ----------------------------------------------------------------------------------------------------


@pytest.fixture
def cli(monkeypatch, tmp_path):
    """gcp.main() reading a filled-in copy of the config, with gcloud and docker 'installed'."""
    monkeypatch.setattr(gcp, "DEPLOY_DIR", filled("production", tmp_path))
    monkeypatch.setattr(gcp, "RENDERED", tmp_path / "rendered")
    monkeypatch.setattr(gcp.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    return tmp_path


def test_cli_dry_run_prints_the_plan_and_runs_nothing(cli, capsys):
    run = FakeRun()
    code = gcp.main(["setup", "--env", "production", "--dry-run"], run=run, input_fn=lambda _: pytest.fail("must not ask"))
    assert code == 0 and run.calls == []
    assert "gcloud services enable" in capsys.readouterr().out


def test_cli_wrong_confirmation_changes_nothing(cli):
    run = FakeRun()
    out: list[str] = []
    code = gcp.main(["setup", "--env", "production"], run=run, input_fn=lambda _: "yes", out=out.append)
    assert code == 1
    assert [argv[:3] for argv, _ in run.calls] == [
        ["gcloud", "projects", "describe"]
    ]  # only the read of the project number happened
    assert any("Nothing was changed" in line for line in out)


def test_cli_typing_the_environment_name_runs_the_plan(cli):
    run = FakeRun()
    code = gcp.main(["setup", "--env", "production"], run=run, input_fn=lambda prompt: "production", out=lambda *_: None)
    assert code == 0 and any("services enable" in " ".join(c[0]) for c in run.calls)


def test_cli_logs_are_read_only_and_ask_nothing(cli):
    run = FakeRun()
    code = gcp.main(["logs", "--env", "production"], run=run, input_fn=lambda _: pytest.fail("must not ask"), out=lambda *_: None)
    assert code == 0 and "logging read" in " ".join(run.calls[-1][0])


def test_cli_deploy_refuses_uncommitted_changes(cli):
    def dirty_git(argv, **kw):
        return subprocess.CompletedProcess(argv, 0, stdout=" M file.py\n", stderr="")

    out: list[str] = []
    code = gcp.main(["deploy", "--env", "production"], run=dirty_git, input_fn=lambda _: "production", out=out.append)
    assert code == 1 and any("uncommitted" in line for line in out)


def test_cli_without_gcloud_installed_says_how_to_install_it(cli, monkeypatch):
    monkeypatch.setattr(gcp.shutil, "which", lambda tool: None)
    out: list[str] = []
    assert gcp.main(["setup", "--env", "production"], out=out.append) == 1
    assert any("google-cloud-cli" in line for line in out)


# ---- the deploy files agree with the app's own startup checks ------------------------------------------------------------------

SECRET_SAMPLES = {
    "SECRET_KEY": "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5",
    "DATABASE_URL": "postgres://u:p@aws-0.pooler.supabase.com:6543/postgres",
    "REDIS_URL": "rediss://default:p@x.upstash.io:6379",
}


def test_each_environment_file_produces_a_config_the_app_accepts(cfg):
    """Fill the placeholders and the secrets, as deployment would, and let the real startup checks judge the result."""
    from circuit.config import Config

    values = {e["name"]: e["value"] for e in gcp.container_env(cfg, "123456789") if "value" in e}
    for name in cfg.secrets:
        values[name] = SECRET_SAMPLES.get(name, "sample-value")
    config = Config(_env_file=None, **{k.lower(): v for k, v in values.items()})
    assert config.env == cfg.env
    assert config.database_pooler == "transaction"  # Cloud Run + Supabase pooler


def test_a_secret_the_deploy_mounts_is_a_variable_the_app_reads(cfg):
    from circuit.config import Config

    for name in cfg.secrets:
        assert name.lower() in Config.model_fields, f"{name} is mounted but the app never reads it"


def test_the_llm_key_mounted_is_the_one_for_the_provider_in_use(cfg):
    provider = cfg.env_vars["LLM_PROVIDER"]
    if provider == "none":
        assert not any(name.endswith("_API_KEY") and name != "RESEND_API_KEY" for name in cfg.secrets)
        return
    assert f"{provider.upper()}_API_KEY" in cfg.secrets


def test_cli_runs_every_command_from_the_repository_root(cli):
    run = FakeRun()
    gcp.main(["setup", "--env", "production"], run=run, input_fn=lambda _: "production", out=lambda *_: None)
    assert run.cwds and all(cwd == gcp.REPO for cwd in run.cwds)  # the docker build uses relative paths


def test_the_jobs_listing_shows_every_job_and_marks_the_unbuilt_ones(cli):
    lines: list[str] = []
    assert gcp.main(["jobs", "--env", "production"], out=lines.append) == 0
    text = "\n".join(lines)
    config = gcp.load_config("production", gcp.DEPLOY_DIR)
    for job in config.active_jobs():
        assert job.key in text
    assert "reset-demo" not in text  # demo only
    assert "build-investor-picks" in text and "not built yet" in text


def test_every_committed_deploy_file_is_valid_toml_with_no_repeated_keys():
    import tomllib

    for path in sorted((REPO / "deploy" / "gcp").glob("*.toml")):
        tomllib.loads(path.read_text())  # a key written twice in one table raises here


def test_alert_channels_never_block_a_deploy_but_do_block_make_monitoring(prod):
    prod.monitoring["notification_channels"] = ["<Circuit production on-call email>"]
    assert gcp.find_placeholders(prod, "deploy") == []
    (line,) = gcp.find_placeholders(prod, "monitoring")
    assert "notification_channels" in line and "Cloud Monitoring" in line


def test_the_placeholder_error_lists_each_missing_value_with_a_hint(prod):
    prod.env_vars["CORS_ALLOWED_ORIGINS"] = "<the app origin>"
    prod.env_vars["SUPABASE_URL"] = "<https://xxxx.supabase.co>"
    prod.env_vars["SOMETHING_NEW"] = "<?>"
    lines = gcp.find_placeholders(prod)
    assert len(lines) == 3
    assert any("CORS_ALLOWED_ORIGINS" in x and "exact origin" in x for x in lines)
    assert any("SUPABASE_URL" in x and "Project URL" in x for x in lines)
    assert any("SOMETHING_NEW" in x and "only you know" in x for x in lines)


def test_make_monitoring_with_no_channels_stops_with_a_clear_message(prod):
    prod.monitoring["notification_channels"] = []
    with pytest.raises(Exception, match="No notification channels"):
        gcp.plan_monitoring(prod, "123456789")


def test_production_cors_allows_exactly_the_origin_the_app_is_served_from(prod):
    from urllib.parse import urlparse

    def origin(url):
        u = urlparse(url)
        return f"{u.scheme}://{u.netloc}"

    cors = [o for o in prod.env_vars["CORS_ALLOWED_ORIGINS"].split(",") if o]
    assert cors == [origin(prod.env_vars["APP_URL"])]


def test_links_built_from_the_production_app_url_land_inside_the_app(prod, settings):
    from apps.beta.services import invite_link
    from apps.notifications.unsubscribe import page_url

    settings.APP_URL = prod.env_vars["APP_URL"]
    assert invite_link("ABCD2345").startswith("https://app.circuitapp.net/join?")
    assert page_url("t").startswith("https://app.circuitapp.net/unsubscribe?")
    assert not prod.env_vars["LANDING_URL"].endswith("/app")


def test_production_mounts_no_redis_secret_for_the_beta_but_staging_and_demo_do():
    prod_cfg = gcp.load_config("production", REPO / "deploy" / "gcp")
    assert "REDIS_URL" not in prod_cfg.secrets
    for env in ("staging", "demo"):
        assert "REDIS_URL" in gcp.load_config(env, REPO / "deploy" / "gcp").secrets


def test_a_real_sender_with_angle_brackets_is_not_mistaken_for_a_placeholder(prod):
    prod.env_vars["EMAIL_FROM"] = "Circuit <support@circuitapp.net>"
    assert gcp.find_placeholders(prod) == []
    prod.env_vars["EMAIL_FROM"] = "Circuit <hello@<yourdomain>>"
    assert len(gcp.find_placeholders(prod)) == 1


def test_the_committed_production_file_has_no_placeholders_left_for_a_deploy():
    """Unlike the other tests this does not fill anything in: it is the file as committed, which `make deploy` will read."""
    cfg = gcp.load_config("production", REPO / "deploy" / "gcp")
    assert gcp.find_placeholders(cfg, "deploy") == []


def test_run_iam_bindings_have_no_condition_flag_but_other_bindings_keep_it(prod):
    # `gcloud run jobs|services add-iam-policy-binding` rejects --condition; secrets and projects accept it.
    steps = gcp.plan_setup(prod) + gcp.plan_deploy(prod, "abc", STATE)
    bindings = [s.argv for s in steps if "add-iam-policy-binding" in s.argv]
    run = [a for a in bindings if a[1:2] == ["run"]]
    assert {a[2] for a in run} == {"jobs", "services"}
    assert not any(x.startswith("--condition") for a in run for x in a)
    kept = [a for a in bindings if a[1] in ("secrets", "projects")]
    assert kept and all("--condition=None" in a for a in kept)
