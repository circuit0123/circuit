"""The GitHub Actions pipelines (.github/workflows) and the deploy script's CI mode. Workflows are read as data: no GitHub, no cloud."""

import re

import pytest
import yaml
from django.conf import settings

from tests.unit.test_deploy_config import LATER, STATE, FakeRun, all_argv, cli, filled, gcp, prod  # noqa: F401 (fixtures)

REPO = settings.BASE_DIR.parent
WORKFLOWS = {p.name: yaml.safe_load(p.read_text()) for p in sorted((REPO / ".github" / "workflows").glob("*.yml"))}
RAW = {p.name: p.read_text() for p in sorted((REPO / ".github" / "workflows").glob("*.yml"))}


def triggers(name):
    wf = WORKFLOWS[name]
    return wf.get("on", wf.get(True))  # YAML reads a bare `on:` as the boolean True


def steps(name, job):
    return WORKFLOWS[name]["jobs"][job]["steps"]


def run_text(name, job):
    return "\n".join(s.get("run", "") for s in steps(name, job))


def all_uses(name):
    found = []
    for job in WORKFLOWS[name]["jobs"].values():
        if "uses" in job:
            found.append(job["uses"])
        found += [s["uses"] for s in job.get("steps", []) if "uses" in s]
    return found


# -- CI ------------------------------------------------------------------------------------------
def test_ci_runs_on_every_pull_request_and_on_main():
    on = triggers("ci.yml")
    assert "pull_request" in on and on["push"]["branches"] == ["main"]


def test_ci_runs_ruff_mypy_and_make_check():
    lint, check = run_text("ci.yml", "lint"), run_text("ci.yml", "check")
    assert "ruff check ." in lint and "ruff format --check ." in lint and "mypy ." in lint
    assert re.search(r"^make check$", check, re.M)


def test_ci_caches_uv_and_pnpm():
    check = steps("ci.yml", "check")
    uv = next(s for s in check if s.get("uses", "").startswith("astral-sh/setup-uv"))
    node = next(s for s in check if s.get("uses", "").startswith("actions/setup-node"))
    assert uv["with"]["enable-cache"] is True and "uv.lock" in uv["with"]["cache-dependency-glob"]
    assert node["with"]["cache"] == "pnpm"
    assert any(s.get("uses", "").startswith("pnpm/action-setup") for s in check)


def test_ci_installs_exactly_what_the_lockfiles_say():
    text = RAW["ci.yml"]
    assert "uv sync --directory backend --frozen" in text and "pnpm install --frozen-lockfile" in text


def test_ci_has_one_final_job_that_branch_protection_can_require():
    ci = WORKFLOWS["ci.yml"]["jobs"]["ci"]
    assert ci["needs"] == ["lint", "check"] and ci["if"] == "always()"  # a skipped or failed job must not look green
    assert (
        'needs.lint.result }}" = "success"' in ci["steps"][0]["run"]
        and 'needs.check.result }}" = "success"' in ci["steps"][0]["run"]
    )


def test_ci_starts_the_same_database_as_a_laptop():
    text = RAW["ci.yml"]
    assert (
        "docker/postgres" in text and "docker compose up -d --wait --no-build db redis" in text and "cp .env.example .env" in text
    )
    assert WORKFLOWS["ci.yml"]["env"]["COMPOSE_PROJECT_NAME"] == "circuit"  # the image name compose looks for


# -- keyless deploys -----------------------------------------------------------------------------
def test_no_workflow_holds_or_uses_a_long_lived_cloud_key():
    for name, text in RAW.items():
        for forbidden in (
            "credentials_json",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GCP_SA_KEY",
            "service_account_key",
            "secrets.GCP",
            "secrets.GOOGLE",
        ):
            assert forbidden not in text, f"{name} mentions {forbidden}"


def test_deploy_authenticates_with_workload_identity_federation_and_nothing_else_can_write():
    deploy = WORKFLOWS["deploy.yml"]["jobs"]["deploy"]
    auth = next(s for s in deploy["steps"] if s.get("uses", "").startswith("google-github-actions/auth"))
    assert set(auth["with"]) == {"workload_identity_provider", "service_account"}
    assert deploy["permissions"] == {"contents": "read", "id-token": "write"}
    assert WORKFLOWS["deploy.yml"]["permissions"] == {"contents": "read"}


def test_deploy_builds_both_architectures_and_pushes_the_commit_tag():
    build = next(s for s in steps("deploy.yml", "deploy") if s.get("uses", "").startswith("docker/build-push-action"))
    assert (
        build["with"]["platforms"] == "${{ env.PLATFORMS }}"
        and WORKFLOWS["deploy.yml"]["env"]["PLATFORMS"] == "linux/amd64,linux/arm64"
    )
    assert build["with"]["push"] is True and build["with"]["provenance"] is False
    assert build["with"]["file"] == "docker/backend/Dockerfile" and "steps.image.outputs.image" in build["with"]["tags"]
    assert any(s.get("uses", "").startswith("docker/setup-qemu-action") for s in steps("deploy.yml", "deploy"))


def test_deploy_runs_the_script_that_migrates_smoke_tests_and_rolls_back():
    assert 'python3 scripts/gcp.py deploy --env "$ENVIRONMENT" --yes --no-build' in run_text("deploy.yml", "deploy")


def test_deploy_never_runs_on_red_or_off_main():
    verify = run_text("deploy.yml", "verify")
    assert 'select(.name == "ci")' in verify and "merge-base --is-ancestor" in verify
    assert WORKFLOWS["deploy.yml"]["jobs"]["deploy"]["needs"] == "verify"


def test_deploys_of_one_environment_never_overlap_and_are_never_cut_off():
    group = WORKFLOWS["deploy.yml"]["jobs"]["deploy"]["concurrency"]
    assert group["group"] == "deploy-${{ inputs.environment }}" and group["cancel-in-progress"] is False


def test_the_environment_of_the_job_is_the_input_so_production_waits_for_its_reviewers():
    assert WORKFLOWS["deploy.yml"]["jobs"]["deploy"]["environment"] == "${{ inputs.environment }}"
    prod_job = WORKFLOWS["deploy-production.yml"]["jobs"]["production"]
    assert prod_job["uses"] == "./.github/workflows/deploy.yml" and prod_job["with"]["environment"] == "production"


def test_production_is_manual_only():
    on = triggers("deploy-production.yml")
    assert set(on) == {"workflow_dispatch"}  # no push, no schedule, no workflow_run


def test_staging_follows_green_ci_on_main_and_is_switched_by_a_variable():
    on = triggers("deploy-staging.yml")
    assert on["workflow_run"] == {"workflows": ["ci"], "types": ["completed"], "branches": ["main"]}
    cond = WORKFLOWS["deploy-staging.yml"]["jobs"]["staging"]["if"]
    assert "STAGING_DEPLOY_ENABLED" in cond and "conclusion == 'success'" in cond


def test_demo_deploys_from_release_tags_then_resets_its_data():
    assert triggers("deploy-demo.yml")["push"]["tags"] == ["v*"]
    assert "jobs-run --env demo --job reset_demo --yes" in run_text("deploy-demo.yml", "reset")
    assert WORKFLOWS["deploy-demo.yml"]["jobs"]["reset"]["needs"] == "demo"


def test_workflow_ci_names_match_what_deploys_wait_for():
    assert WORKFLOWS["ci.yml"]["name"] == "ci" and "ci" in WORKFLOWS["ci.yml"]["jobs"]


# -- hygiene -------------------------------------------------------------------------------------
def test_every_action_is_pinned_to_a_version():
    for name in WORKFLOWS:
        for uses in all_uses(name):
            if uses.startswith("./"):
                continue
            ref = uses.split("@", 1)[1]
            assert re.fullmatch(r"v\d+(\.\d+){0,2}|[0-9a-f]{40}", ref), f"{name}: {uses} must be pinned to a version or a commit"


def test_dependabot_keeps_the_actions_up_to_date():
    config = yaml.safe_load((REPO / ".github" / "dependabot.yml").read_text())
    assert {u["package-ecosystem"] for u in config["updates"]} >= {"github-actions", "uv", "npm", "docker"}


def test_untrusted_text_never_reaches_a_shell():
    """`${{ inputs.x }}` or `${{ github.event... }}` pasted into a script is command injection; it goes through env: instead."""
    for name, wf in WORKFLOWS.items():
        for job_id, job in wf["jobs"].items():
            for step in job.get("steps", []):
                script = step.get("run", "")
                assert "${{ inputs." not in script and "${{ github.event" not in script and "${{ github.head_ref" not in script, (
                    name,
                    job_id,
                )


def test_workflows_only_call_make_targets_that_exist():
    makefile = (REPO / "Makefile").read_text()
    targets = set(re.findall(r"^([a-zA-Z0-9_-]+):", makefile, re.M))
    for text in RAW.values():
        for target in re.findall(r"^\s*(?:run: )?make ([a-z-]+)", text, re.M):
            assert target in targets


# -- the deploy script in CI mode ----------------------------------------------------------------
def test_yes_is_refused_outside_ci(cli, capsys):  # noqa: F811
    code = gcp.main(["deploy", "--env", "production", "--yes", "--no-build"], run=FakeRun(), environ={}, out=print)
    assert code == 1 and "only for the CI pipeline" in capsys.readouterr().out


def test_yes_in_ci_skips_the_typed_confirmation(cli):  # noqa: F811
    run = FakeRun()
    code = gcp.main(
        ["jobs-run", "--env", "production", "--job", "compute_matches", "--yes"],
        run=run,
        input_fn=lambda _: pytest.fail("must not ask"),
        environ={"CI": "true"},
        out=lambda *_: None,
    )
    assert code == 0 and any("jobs execute" in " ".join(c[0]) for c in run.calls)


def test_the_image_command_prints_one_line_for_the_workflow(cli, capsys, monkeypatch):  # noqa: F811
    monkeypatch.setattr(gcp, "git_tag", lambda run, allow_dirty=False: "abc123def456")
    assert gcp.main(["image", "--env", "production"], run=FakeRun(), out=print) == 0
    assert capsys.readouterr().out.strip() == "asia-south1-docker.pkg.dev/circuit-test-1/circuit/api:abc123def456"


def test_no_build_checks_the_image_is_there_instead_of_building(prod):  # noqa: F811
    lines = all_argv(gcp.plan_deploy(prod, "abc", LATER, build=False))
    assert not any(line.startswith("docker buildx") for line in lines)
    assert any("artifacts docker images describe" in line and "api:abc" in line for line in lines)
    with_build = all_argv(gcp.plan_deploy(prod, "abc", LATER))
    assert any(line.startswith("docker buildx build") for line in with_build)


def test_a_missing_image_stops_before_anything_changes(prod):  # noqa: F811
    class NoImage(FakeRun):
        def __call__(self, argv, **kw):
            done = super().__call__(argv, **kw)
            if "images describe" in " ".join(argv):
                done.stdout = ""
            return done

    run = NoImage()
    with pytest.raises(gcp.DeployError, match="not in Artifact Registry"):
        gcp.run_plan(gcp.plan_deploy(prod, "abc", LATER, build=False), run, out=lambda *_: None)
    assert not any("jobs execute" in " ".join(c[0]) for c in run.calls)


LIVE = "smoke.py https://circuit-production-api-"  # the live address; the private test address is https://next---circuit-production-api-...


def live_smoke(plan):
    return [s for s in plan if s.argv[1].endswith("smoke.py") and "---" not in " ".join(s.argv)][-1]


def test_a_failed_live_smoke_test_sends_traffic_back_by_itself(prod):  # noqa: F811
    plan = gcp.plan_deploy(prod, "abc", LATER)
    (undo,) = live_smoke(plan).on_failure
    assert undo.argv[:5] == ["gcloud", "run", "services", "update-traffic", prod.service_name]
    assert f"--to-revisions={LATER.serving_revision}=100" in undo.argv
    run = FakeRun(fail_on=LIVE)
    out: list[str] = []
    with pytest.raises(gcp.DeployError, match="previous version is serving again"):
        gcp.run_plan(plan, run, out=out.append)
    ran = [" ".join(c[0]) for c in run.calls]
    moved = [i for i, r in enumerate(ran) if "update-traffic" in r and "--to-latest" in r]
    back = [i for i, r in enumerate(ran) if f"--to-revisions={LATER.serving_revision}=100" in r]
    assert moved and back and back[0] > moved[0]
    assert not any("scheduler" in r for r in ran)  # the jobs are not touched after a failed deploy
    assert any("Rolling back automatically" in line for line in out)


def test_a_failed_private_smoke_test_never_moves_traffic(prod):  # noqa: F811
    run = FakeRun(fail_on="---circuit-production-api")
    with pytest.raises(gcp.DeployError):
        gcp.run_plan(gcp.plan_deploy(prod, "abc", LATER), run, out=lambda *_: None)
    assert not any("update-traffic" in " ".join(c[0]) for c in run.calls)


def test_a_failed_rollback_says_so(prod):  # noqa: F811
    plan = gcp.plan_deploy(prod, "abc", LATER)

    class Both(FakeRun):
        def __call__(self, argv, **kw):
            line = " ".join(argv)
            self.fail_on = LIVE if "smoke.py" in line else f"--to-revisions={LATER.serving_revision}"
            return super().__call__(argv, **kw)

    with pytest.raises(gcp.DeployError, match="rollback ALSO failed"):
        gcp.run_plan(plan, Both(), out=lambda *_: None)


def test_the_first_deploy_has_nothing_to_roll_back_to(prod):  # noqa: F811
    assert live_smoke(gcp.plan_deploy(prod, "abc", STATE)).on_failure == []


def test_setup_trusts_only_our_repository_and_only_per_environment(prod):  # noqa: F811
    plan = all_argv(gcp.plan_setup(prod, "123456789"))
    provider = next(line for line in plan if "providers create-oidc" in line)
    assert "assertion.repository=='circuit0123/circuit'" in provider and "token.actions.githubusercontent.com" in provider
    binding = next(line for line in plan if "roles/iam.workloadIdentityUser" in line)
    assert "workloadIdentityPools/circuit-github/attribute.environment/production" in binding and "projects/123456789/" in binding
    assert not any("roles/iam.workloadIdentityUser" in line and "attribute.repository" in line for line in plan)  # not repo-wide


def test_the_deploy_account_can_deploy_but_not_read_secrets(prod):  # noqa: F811
    roles = gcp.DEPLOY_ROLES
    assert "roles/run.admin" in roles and "roles/artifactregistry.writer" in roles and "roles/cloudscheduler.admin" in roles
    assert not [r for r in roles if "secretAccessor" in r or r in ("roles/owner", "roles/editor")]
    plan = all_argv(gcp.plan_setup(prod, "1"))
    on_runtime = [line for line in plan if prod.runtime_sa in line and "roles/iam.serviceAccountUser" in line]
    assert on_runtime and all(f"--member=serviceAccount:{prod.deploy_sa}" in line for line in on_runtime)


def test_setup_prints_the_two_github_variables(prod):  # noqa: F811
    assert gcp.ci_variables(prod, "123456789") == {
        "WIF_PROVIDER": "projects/123456789/locations/global/workloadIdentityPools/circuit-github/providers/github",
        "DEPLOY_SA": "circuit-deploy-production@circuit-test-1.iam.gserviceaccount.com",
    }
