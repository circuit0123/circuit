#!/usr/bin/env python3
"""Deploy Circuit's backend to Google Cloud (Cloud Run + Cloud Scheduler + Secret Manager + Artifact Registry).

Run it through make (COMMANDS.md): make gcp-setup | deploy | rollback | secret | jobs-run | logs | monitoring, each with ENV=production.

How it works, so it is never a black box:
  1. It reads deploy/gcp/app.toml (shared) and deploy/gcp/<env>.toml (yours) and builds a PLAN: an ordered list of steps.
  2. It prints every step with the exact command and one sentence on why.
  3. It asks you to type the environment name. Nothing changes before that.
  4. It runs the steps in order and stops at the first failure. Every step is safe to run again.

`--dry-run` prints the plan and stops, and works without gcloud installed. The plan functions below take plain data and return
plain data, which is how tests/unit/test_deploy_config.py checks them without any cloud account.

Only the Python standard library is used. Nothing here ever puts a secret value in a command line: secret values are typed at a
hidden prompt and passed to gcloud on its standard input.
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))  # so the helper next to this file imports however this file was loaded
import gcp_monitoring  # noqa: E402
DEPLOY_DIR = REPO / "deploy" / "gcp"
RENDERED = DEPLOY_DIR / ".rendered"  # manifests written for gcloud to read; gitignored, safe to delete
ENVS = ("production", "staging", "demo")
PLACEHOLDER = re.compile(r"<[^<>]+>")
APIS = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "billingbudgets.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
]
KEEP_IMAGES = 5


class DeployError(Exception):
    """Something the person can fix; printed without a traceback."""


# ---- configuration --------------------------------------------------------------------------------------------------------


@dataclass
class Job:
    key: str  # "compute-matches": also the tail of the Cloud Run Job and Scheduler names
    command: str
    args: list[str] = field(default_factory=list)
    schedule: str | None = None
    enabled: bool = True
    envs: list[str] | None = None
    manual: bool = False
    bundled: bool = False
    cpu: str = "1"
    memory: str = "1Gi"
    timeout_seconds: int = 600
    max_retries: int = 1


@dataclass
class Cfg:
    env: str
    project: str
    region: str
    billing_account: str
    budget: str
    service: dict
    secrets: list[str]
    env_vars: dict[str, str]
    jobs: dict[str, Job]  # every job of the file, including disabled ones and ones for other environments
    monitoring: dict = field(default_factory=dict)  # [monitoring] of <env>.toml: notification_channels = ["display name", ...]

    # -- names: one place, so every command and every test agrees --
    @property
    def service_name(self) -> str:
        return f"circuit-{self.env}-api"

    def job_name(self, key: str) -> str:
        return f"circuit-{self.env}-{key}"

    def secret_id(self, name: str) -> str:
        return f"circuit-{self.env}-" + name.lower().replace("_", "-")

    @property
    def runtime_sa(self) -> str:
        return f"circuit-run-{self.env}@{self.project}.iam.gserviceaccount.com"

    @property
    def scheduler_sa(self) -> str:
        return f"circuit-sched-{self.env}@{self.project}.iam.gserviceaccount.com"

    @property
    def registry_host(self) -> str:
        return f"{self.region}-docker.pkg.dev"

    def image(self, tag: str) -> str:
        return f"{self.registry_host}/{self.project}/circuit/api:{tag}"

    def active_jobs(self) -> list[Job]:
        """Jobs that exist in this environment: enabled, and not limited to other environments."""
        return [j for j in self.jobs.values() if j.enabled and (j.envs is None or self.env in j.envs)]

    def find_job(self, name: str) -> Job:
        key = name.replace("_", "-")
        for job in self.active_jobs():
            if key in (job.key, job.command.replace("_", "-")):
                return job
        names = ", ".join(sorted(j.key for j in self.active_jobs()))
        raise DeployError(f"No job called '{name}' in {self.env}. Jobs: {names}")


def load_config(env: str, deploy_dir: Path | None = None) -> Cfg:
    deploy_dir = deploy_dir or DEPLOY_DIR
    if env not in ENVS:
        raise DeployError(f"ENV must be one of {', '.join(ENVS)} (got '{env}')")
    shared = tomllib.loads((deploy_dir / "app.toml").read_text())
    mine = tomllib.loads((deploy_dir / f"{env}.toml").read_text())
    jobs = {}
    for key, raw in shared.get("jobs", {}).items():
        jobs[key] = Job(key=key, **raw)
    service = {**shared["service"], **mine.get("service", {})}
    # `secrets` sits inside [service] in both files: the shared list plus this environment's extras (the LLM key, the email key).
    secrets = [*shared["service"].get("secrets", []), *mine.get("service", {}).get("secrets", [])]
    service.pop("secrets", None)
    env_vars = {**shared.get("env", {}), **mine.get("env", {})}
    project = mine["project"]
    return Cfg(
        env=env,
        project=project["id"],
        region=project["region"],
        billing_account=project["billing_account"],
        budget=project["budget"],
        service=service,
        secrets=secrets,
        env_vars={k: str(v) for k, v in env_vars.items()},
        jobs=jobs,
        monitoring=mine.get("monitoring", {}),
    )


def cron_interval_minutes(schedule: str) -> int:
    """How often a Scheduler cron fires, in minutes, for the shapes app.toml uses: "*/N * * * *", "M * * * *", "M */N * * *",
    "M H * * *" (daily) and "M H * * D" (weekly). Anything else stops with a message, so a job can never silently lose its watcher."""
    fields = schedule.split()
    if len(fields) != 5:
        raise DeployError(f"'{schedule}' is not a 5-field cron")
    minute, hour, dom, mon, dow = fields
    if dom == "*" and mon == "*":
        if minute.startswith("*/") and hour == "*" and dow == "*":
            return int(minute[2:])
        if minute.isdigit() and hour == "*" and dow == "*":
            return 60
        if minute.isdigit() and hour.startswith("*/") and dow == "*":
            return int(hour[2:]) * 60
        if minute.isdigit() and hour.isdigit() and dow == "*":
            return 1440
        if minute.isdigit() and hour.isdigit() and dow.isdigit():
            return 10080
    raise DeployError(f"Cannot work out how often '{schedule}' runs. Teach cron_interval_minutes() this shape.")


def job_intervals(cfg: Cfg) -> dict[str, int]:
    """{command: minutes between runs} for every scheduled job in this environment; the commands a bundle runs get the bundle's.
    Becomes JOB_INTERVALS, which job health (backend/core/jobhealth.py) compares each job's last success against."""
    out: dict[str, int] = {}
    for job in cfg.active_jobs():
        if not job.schedule:
            continue
        minutes = cron_interval_minutes(job.schedule)
        for command in job.args if job.command == "run_jobs" else [job.command]:
            out[command] = minutes
    return dict(sorted(out.items()))


def find_placeholders(cfg: Cfg) -> list[str]:
    """Every <angle bracket> value still waiting for you, so a half-filled file never reaches gcloud."""
    found = []
    for label, value in [("project.id", cfg.project), ("project.billing_account", cfg.billing_account)]:
        if PLACEHOLDER.search(value):
            found.append(f"{label} = {value}")
    for key, value in sorted(cfg.env_vars.items()):
        if PLACEHOLDER.search(value):
            found.append(f"env.{key} = {value}")
    for channel in cfg.monitoring.get("notification_channels", []):
        if PLACEHOLDER.search(channel):
            found.append(f"monitoring.notification_channels = {channel}")
    return found


# ---- plans ----------------------------------------------------------------------------------------------------------------


@dataclass
class Step:
    argv: list[str]
    why: str
    changes: bool = True  # False = only reads (checks, lookups, logs)
    local: bool = False  # runs on this computer (docker, smoke test), not in Google Cloud
    stdin_prompt: str | None = None  # value is typed at a hidden prompt and piped to the command; never shown, never an argument
    skip_if: list[str] | None = None  # read-only probe; if it succeeds with output, the step is already done and is skipped
    use_if_exists: tuple[list[str], list[str]] | None = None  # (probe, argv to run instead when the probe succeeds)
    must_have_output: str | None = None  # read-only check; fails with this message when the command prints nothing
    optional: bool = False  # a failure is a warning, not a stop
    files: dict[Path, str] = field(default_factory=dict)  # written just before the step (manifests)


def gcloud(*args: str) -> list[str]:
    return ["gcloud", *args]


def _p(cfg: Cfg) -> list[str]:
    return ["--project", cfg.project]


def _r(cfg: Cfg) -> list[str]:
    return ["--region", cfg.region]


def yaml_dump(value, indent: int = 0) -> str:
    """Tiny YAML writer for the manifests (dicts, lists, strings, numbers, booleans). Strings are always double-quoted, which is
    valid YAML, so values like "0" or "true" can never be misread. Avoids a third-party YAML dependency."""
    pad = "  " * indent

    def scalar(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int | float):
            return str(v)
        if isinstance(v, dict):
            return "{}"
        if isinstance(v, list):
            return "[]"
        return json.dumps(str(v), ensure_ascii=False)

    def key(k: str) -> str:
        return k if re.fullmatch(r"[A-Za-z0-9_./-]+", k) else json.dumps(k)

    lines: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, dict | list) and v:
                lines.append(f"{pad}{key(k)}:")
                lines.append(yaml_dump(v, indent + 1))
            else:
                lines.append(f"{pad}{key(k)}: {scalar(v)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item:
                body = yaml_dump(item, indent + 1).split("\n")
                lines.append(f"{pad}- {body[0].lstrip()}")
                lines.extend(body[1:])
            else:
                lines.append(f"{pad}- {scalar(item)}")
    else:
        lines.append(f"{pad}{scalar(value)}")
    return "\n".join(lines)


def api_url(cfg: Cfg, project_number: str) -> str:
    """The service's public address. Cloud Run addresses are predictable: <service>-<project number>.<region>.run.app."""
    return f"https://{cfg.service_name}-{project_number}.{cfg.region}.run.app"


def tagged_url(cfg: Cfg, project_number: str, tag: str) -> str:
    return f"https://{tag}---{cfg.service_name}-{project_number}.{cfg.region}.run.app"


def container_env(cfg: Cfg, project_number: str, release: str = "") -> list[dict]:
    """Plain variables, then the secrets. A value of "auto" for API_URL becomes the service's own address.
    `release` (the image tag, i.e. the git commit) is what Sentry tags every error with."""
    values = dict(cfg.env_vars)
    if release:
        values["RELEASE"] = release
    values["JOB_INTERVALS"] = ",".join(f"{name}:{minutes}" for name, minutes in job_intervals(cfg).items())
    if values.get("API_URL") == "auto":
        values["API_URL"] = api_url(cfg, project_number)
    values["GOOGLE_CLOUD_PROJECT"] = cfg.project  # lets log lines link to Cloud Trace
    out = [{"name": k, "value": v} for k, v in sorted(values.items()) if v != ""]
    out += [{"name": s, "valueFrom": {"secretKeyRef": {"name": cfg.secret_id(s), "key": "latest"}}} for s in cfg.secrets]
    return out


def release_of(image: str) -> str:
    """'.../circuit/api:1a2b3c4d5e6f' -> '1a2b3c4d5e6f'."""
    return image.rpartition(":")[2]


def service_manifest(cfg: Cfg, image: str, project_number: str, serving_revision: str | None) -> dict:
    s = cfg.service
    probe_port = {"port": 8080}
    traffic = [{"latestRevision": True, "percent": 100}]
    if serving_revision:  # a later deploy: the new revision gets 0% and a test address until the smoke test passes
        traffic = [{"revisionName": serving_revision, "percent": 100}, {"latestRevision": True, "percent": 0, "tag": "next"}]
    return {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {"name": cfg.service_name, "labels": {"cloud.googleapis.com/location": cfg.region}},
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "autoscaling.knative.dev/minScale": str(s["min_instances"]),
                        "autoscaling.knative.dev/maxScale": str(s["max_instances"]),
                        "run.googleapis.com/cpu-throttling": "true" if s["cpu_throttling"] else "false",
                        "run.googleapis.com/startup-cpu-boost": "true" if s["cpu_boost"] else "false",
                    }
                },
                "spec": {
                    "serviceAccountName": cfg.runtime_sa,
                    "containerConcurrency": s["concurrency"],
                    "timeoutSeconds": s["timeout_seconds"],
                    "containers": [
                        {
                            "image": image,
                            "ports": [{"containerPort": 8080}],
                            "env": container_env(cfg, project_number, release_of(image)),
                            "resources": {"limits": {"cpu": s["cpu"], "memory": s["memory"]}},
                            "startupProbe": {
                                "httpGet": {"path": s["startup_probe_path"], **probe_port},
                                "periodSeconds": 3,
                                "timeoutSeconds": 3,
                                "failureThreshold": 20,
                            },
                            "livenessProbe": {
                                "httpGet": {"path": s["liveness_probe_path"], **probe_port},
                                "periodSeconds": 30,
                                "timeoutSeconds": 3,
                                "failureThreshold": 3,
                            },
                        }
                    ],
                },
            },
            "traffic": traffic,
        },
    }


def job_manifest(cfg: Cfg, job: Job, image: str, project_number: str) -> dict:
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {"name": cfg.job_name(job.key), "labels": {"cloud.googleapis.com/location": cfg.region}},
        "spec": {
            "template": {
                "spec": {
                    "template": {
                        "spec": {
                            "maxRetries": job.max_retries,
                            "timeoutSeconds": job.timeout_seconds,
                            "serviceAccountName": cfg.runtime_sa,
                            "containers": [
                                {
                                    "image": image,
                                    "command": ["python", "manage.py", job.command],
                                    "args": list(job.args),
                                    "env": container_env(cfg, project_number, release_of(image)),
                                    "resources": {"limits": {"cpu": job.cpu, "memory": job.memory}},
                                }
                            ],
                        }
                    }
                }
            }
        },
    }


def plan_setup(cfg: Cfg) -> list[Step]:
    """One-time project setup. Rerunning it only creates what is missing."""
    p = _p(cfg)
    steps = [
        Step(
            gcloud("services", "enable", *APIS, *p),
            "Turn on the Google Cloud services Circuit uses (Cloud Run, Artifact Registry, Secret Manager, Scheduler, ...). Free.",
        ),
        Step(
            gcloud(
                "artifacts",
                "repositories",
                "create",
                "circuit",
                "--repository-format=docker",
                f"--location={cfg.region}",
                "--description=Circuit backend images",
                *p,
            ),
            "Create the private place where the backend images are stored.",
            skip_if=gcloud(
                "artifacts", "repositories", "describe", "circuit", f"--location={cfg.region}", *p, "--format=value(name)"
            ),
        ),
        Step(
            gcloud(
                "artifacts",
                "repositories",
                "set-cleanup-policies",
                "circuit",
                f"--location={cfg.region}",
                f"--policy={RENDERED / cfg.env / 'cleanup-policy.json'}",
                *p,
            ),
            f"Keep only the newest {KEEP_IMAGES} images, so old ones do not pile up and cost storage. (Nice to have: a failure here does not stop setup.)",
            optional=True,
            files={
                RENDERED / cfg.env / "cleanup-policy.json": json.dumps(
                    [
                        {"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": KEEP_IMAGES}},
                        {"name": "delete-the-rest", "action": {"type": "Delete"}, "condition": {"tagState": "ANY"}},
                    ],
                    indent=2,
                )
            },
        ),
    ]
    for sa_id, label in [
        (f"circuit-run-{cfg.env}", "runs the API and the jobs"),
        (f"circuit-sched-{cfg.env}", "may only start jobs"),
    ]:
        email = f"{sa_id}@{cfg.project}.iam.gserviceaccount.com"
        steps.append(
            Step(
                gcloud("iam", "service-accounts", "create", sa_id, f"--display-name=Circuit {cfg.env}: {label}", *p),
                f"Create the service account that {label}. It starts with no permissions at all.",
                skip_if=gcloud("iam", "service-accounts", "describe", email, *p, "--format=value(email)"),
            )
        )
    for name in cfg.secrets:
        sid = cfg.secret_id(name)
        steps.append(
            Step(
                gcloud(
                    "secrets",
                    "create",
                    sid,
                    "--replication-policy=user-managed",
                    f"--locations={cfg.region}",
                    *p,
                ),
                f"Create an empty slot for {name}, stored only in {cfg.region} (India). You fill it later with: make secret NAME={name}",
                skip_if=gcloud("secrets", "describe", sid, *p, "--format=value(name)"),
            )
        )
        steps.append(
            Step(
                gcloud(
                    "secrets",
                    "add-iam-policy-binding",
                    sid,
                    f"--member=serviceAccount:{cfg.runtime_sa}",
                    "--role=roles/secretmanager.secretAccessor",
                    *p,
                    "--condition=None",
                ),
                f"Let the runtime service account read {name}, and no other secret.",
            )
        )
    budget_name = f"circuit-{cfg.env}-budget"
    steps.append(
        Step(
            gcloud(
                "billing",
                "budgets",
                "create",
                f"--billing-account={cfg.billing_account}",
                f"--display-name={budget_name}",
                f"--budget-amount={cfg.budget}",
                "--threshold-rule=percent=0.5",
                "--threshold-rule=percent=0.8",
                "--threshold-rule=percent=1.0",
                f"--filter-projects=projects/{cfg.project}",
                "--credit-types-treatment=exclude-all-credits",
            ),
            f"Email the billing admins at 50%, 80% and 100% of {cfg.budget} a month. 'exclude-all-credits' makes it count real "
            "usage even while free credits pay the bill, otherwise it would never fire. It warns; it does not stop spending.",
            skip_if=gcloud(
                "billing",
                "budgets",
                "list",
                f"--billing-account={cfg.billing_account}",
                f"--filter=displayName={budget_name}",
                "--format=value(name)",
            ),
        )
    )
    return steps


def plan_monitoring(cfg: Cfg, project_number: str, lenient: bool = False) -> list[Step]:
    """Uptime checks, log-based metrics and alert policies from infra/monitoring/, created or updated by name.
    `lenient` (dry runs) lets an unfilled <placeholder> through so the plan can still be shown."""
    api = cfg.env_vars.get("API_URL", "")
    values = gcp_monitoring.variables(
        project=cfg.project,
        env=cfg.env,
        service=cfg.service_name,
        api_url=api_url(cfg, project_number) if api == "auto" else api,
        app_url=cfg.env_vars.get("APP_URL", ""),
        landing_url=cfg.env_vars.get("LANDING_URL", ""),
        channels=list(cfg.monitoring.get("notification_channels", [])),
        lenient=lenient,
    )
    rendered = gcp_monitoring.render(values)
    folder = RENDERED / cfg.env / "monitoring"
    return [
        Step(
            gcloud("services", "enable", "monitoring.googleapis.com", *_p(cfg)),
            "Turn on Cloud Monitoring (free for what Circuit uses: a few uptime checks and alert policies).",
        ),
        Step(
            [
                sys.executable,
                str(REPO / "scripts" / "gcp_monitoring.py"),
                "apply",
                "--project",
                cfg.project,
                "--dir",
                str(folder),
                "--files",
                *rendered,
            ],
            f"Create or update {len(rendered)} monitoring objects in {cfg.env} (log-based metrics, uptime checks, alert policies), "
            "found by name, so running this twice changes nothing the second time. It sends alerts to the notification channels "
            f"{', '.join(cfg.monitoring.get('notification_channels', []))}; a channel that does not exist stops the run.",
            local=True,
            files={folder / name: text for name, text in rendered.items()},
        ),
    ]


@dataclass
class DeployState:
    """What exists right now. Read from Google Cloud at run time; tests pass it in."""

    project_number: str
    serving_revision: str | None = None  # None = first deploy (no service yet)


def _job_steps(cfg: Cfg, image: str, state: DeployState, jobs: list[Job]) -> list[Step]:
    """For each job: create/update the Cloud Run Job; if it is scheduled, allow the scheduler account to start it and create/update
    the Scheduler trigger."""
    p, r = _p(cfg), _r(cfg)
    steps = []
    for job in jobs:
        name = cfg.job_name(job.key)
        path = RENDERED / cfg.env / f"job-{job.key}.yaml"
        steps.append(
            Step(
                gcloud("run", "jobs", "replace", str(path), *r, *p),
                f"Create or update the job '{name}' to run: python manage.py {' '.join([job.command, *job.args])}",
                files={path: yaml_dump(job_manifest(cfg, job, image, state.project_number)) + "\n"},
            )
        )
        if not job.schedule:
            continue
        steps.append(
            Step(
                gcloud(
                    "run",
                    "jobs",
                    "add-iam-policy-binding",
                    name,
                    f"--member=serviceAccount:{cfg.scheduler_sa}",
                    "--role=roles/run.invoker",
                    *r,
                    *p,
                    "--condition=None",
                ),
                f"Let the scheduler account start '{name}' and nothing else.",
            )
        )
        uri = f"https://run.googleapis.com/v2/projects/{cfg.project}/locations/{cfg.region}/jobs/{name}:run"
        common = [
            name,
            f"--location={cfg.region}",
            f"--schedule={job.schedule}",
            "--time-zone=Asia/Kolkata",
            f"--uri={uri}",
            "--http-method=POST",
            f"--oauth-service-account-email={cfg.scheduler_sa}",
            "--headers=Content-Type=application/json",
            "--message-body={}",
            *p,
        ]
        steps.append(
            Step(
                gcloud("scheduler", "jobs", "create", "http", *common),
                f"Start '{name}' on schedule '{job.schedule}' (India time). If the trigger exists, it is updated instead.",
                use_if_exists=(
                    gcloud("scheduler", "jobs", "describe", name, f"--location={cfg.region}", *p, "--format=value(name)"),
                    gcloud("scheduler", "jobs", "update", "http", *common),
                ),
            )
        )
    return steps


def plan_deploy(cfg: Cfg, tag: str, state: DeployState, smoke_origins: list[str] | None = None) -> list[Step]:
    p, r = _p(cfg), _r(cfg)
    image = cfg.image(tag)
    smoke = [sys.executable, str(REPO / "scripts" / "smoke.py")]
    origins = [a for o in (smoke_origins or []) for a in ("--origin", o)]
    steps: list[Step] = []
    for name in cfg.secrets:
        sid = cfg.secret_id(name)
        steps.append(
            Step(
                gcloud("secrets", "versions", "list", sid, "--filter=state=ENABLED", "--limit=1", "--format=value(name)", *p),
                f"Check that {name} has a value (Cloud Run cannot start a revision that mounts an empty secret).",
                changes=False,
                must_have_output=f"{name} has no value yet. Set it first:  make secret ENV={cfg.env} NAME={name}",
            )
        )
    steps += [
        Step(
            gcloud("auth", "configure-docker", cfg.registry_host, "--quiet"),
            "Let docker on this computer push to your Artifact Registry (adds one line to ~/.docker/config.json).",
        ),
        Step(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/amd64",
                "--provenance=false",
                "-f",
                "docker/backend/Dockerfile",
                "-t",
                image,
                "--push",
                ".",
            ],
            "Build the backend image for Cloud Run (x86_64) from this commit and upload it. The first upload is large (hundreds of MB).",
            local=True,
        ),
    ]
    migrate = cfg.jobs["migrate"]
    steps += _job_steps(cfg, image, state, [migrate])
    steps.append(
        Step(
            gcloud("run", "jobs", "execute", cfg.job_name("migrate"), *r, *p, "--wait"),
            "Run database migrations with the NEW code and wait for them to finish. If this fails, nothing else happens and the "
            "running site is untouched.",
        )
    )
    first = state.serving_revision is None
    manifest_path = RENDERED / cfg.env / "service.yaml"
    steps.append(
        Step(
            gcloud("run", "services", "replace", str(manifest_path), *r, *p),
            "Create the API service."
            if first
            else "Add a new API revision. It gets 0% of traffic and a private test address until it passes the smoke test.",
            files={manifest_path: yaml_dump(service_manifest(cfg, image, state.project_number, state.serving_revision)) + "\n"},
        )
    )
    steps.append(
        Step(
            gcloud(
                "run",
                "services",
                "add-iam-policy-binding",
                cfg.service_name,
                "--member=allUsers",
                "--role=roles/run.invoker",
                *r,
                *p,
                "--condition=None",
            ),
            "Let the internet reach the API (members still need a valid sign-in token for everything except the public endpoints).",
        )
    )
    if not first:
        steps.append(
            Step(
                [*smoke, tagged_url(cfg, state.project_number, "next"), *origins],
                "Smoke-test the new revision on its private test address before any member reaches it.",
                changes=False,
                local=True,
            )
        )
        steps.append(
            Step(
                gcloud("run", "services", "update-traffic", cfg.service_name, "--to-latest", *r, *p),
                "Send 100% of traffic to the new revision.",
            )
        )
        steps.append(
            Step(
                gcloud("run", "services", "update-traffic", cfg.service_name, "--remove-tags=next", *r, *p),
                "Remove the private test address.",
            )
        )
    steps.append(
        Step(
            [*smoke, api_url(cfg, state.project_number), *origins],
            "Smoke-test the live address.",
            changes=False,
            local=True,
        )
    )
    steps += _job_steps(cfg, image, state, [j for j in cfg.active_jobs() if j.key != "migrate"])
    return steps


@dataclass
class Revision:
    name: str
    image: str


def choose_rollback(revisions: list[Revision], serving: str, target: str | None) -> Revision:
    """`revisions` newest first. Default target = the revision just before the one that is serving."""
    names = [rev.name for rev in revisions]
    if serving not in names:
        raise DeployError(
            f"The serving revision {serving} is not in the revision list, so there is no 'previous' to pick. Use REVISION=..."
        )
    if target:
        for rev in revisions:
            if rev.name == target:
                if rev.name == serving:
                    raise DeployError(f"{target} is already serving.")
                return rev
        raise DeployError(f"No revision called {target}. Revisions: {', '.join(names)}")
    older = revisions[names.index(serving) + 1 :]
    if not older:
        raise DeployError("There is no older revision to go back to.")
    return older[0]


def plan_rollback(cfg: Cfg, target: Revision, state: DeployState, smoke_origins: list[str] | None = None) -> list[Step]:
    p, r = _p(cfg), _r(cfg)
    origins = [a for o in (smoke_origins or []) for a in ("--origin", o)]
    steps = [
        Step(
            gcloud("run", "services", "update-traffic", cfg.service_name, f"--to-revisions={target.name}=100", *r, *p),
            f"Send 100% of traffic back to {target.name}. Takes effect in seconds. Database migrations are NOT undone: "
            "each migration is written so the previous code still works with it.",
        )
    ]
    for job in cfg.active_jobs():
        steps.append(
            Step(
                gcloud("run", "jobs", "update", cfg.job_name(job.key), f"--image={target.image}", *r, *p),
                f"Point the job '{cfg.job_name(job.key)}' at the same older image, so jobs and API run the same code.",
            )
        )
    steps.append(
        Step(
            [sys.executable, str(REPO / "scripts" / "smoke.py"), api_url(cfg, state.project_number), *origins],
            "Smoke-test the live address.",
            changes=False,
            local=True,
        )
    )
    return steps


def plan_secret(cfg: Cfg, name: str) -> list[Step]:
    name = name.upper()
    if name not in cfg.secrets:
        raise DeployError(f"'{name}' is not a secret of {cfg.env}. Secrets: {', '.join(cfg.secrets)}")
    return [
        Step(
            gcloud("secrets", "versions", "add", cfg.secret_id(name), "--data-file=-", *_p(cfg)),
            f"Store a new value for {name} as a new version. Older versions stay, so you can go back. The value is typed at a hidden "
            "prompt and goes to gcloud on its standard input; it is not in this command line, your shell history or the process list.",
            stdin_prompt=f"Value for {name} (hidden)",
        )
    ]


def plan_jobs_run(cfg: Cfg, name: str) -> list[Step]:
    job = cfg.find_job(name)
    return [
        Step(
            gcloud("run", "jobs", "execute", cfg.job_name(job.key), *_r(cfg), *_p(cfg), "--wait"),
            f"Run '{cfg.job_name(job.key)}' once, now, and wait for it: python manage.py {' '.join([job.command, *job.args])}",
        )
    ]


def plan_logs(cfg: Cfg, job: str | None, limit: int) -> list[Step]:
    if job:
        j = cfg.find_job(job)
        flt = f'resource.type="cloud_run_job" AND resource.labels.job_name="{cfg.job_name(j.key)}"'
    else:
        flt = f'resource.type="cloud_run_revision" AND resource.labels.service_name="{cfg.service_name}"'
    return [
        Step(
            gcloud(
                "logging",
                "read",
                flt,
                f"--limit={limit}",
                "--order=desc",
                "--format=value(timestamp,severity,jsonPayload.message,jsonPayload.path,jsonPayload.status)",
                *_p(cfg),
            ),
            "Show the newest log lines (newest first).",
            changes=False,
        )
    ]


# ---- running a plan -------------------------------------------------------------------------------------------------------

Runner = Callable[..., subprocess.CompletedProcess]


def print_plan(steps: list[Step], out=print, show_files: bool = False) -> None:
    for n, step in enumerate(steps, 1):
        kind = "changes things" if step.changes else "read-only"
        where = "on this computer" if step.local else "in Google Cloud"
        out(f"\nStep {n} of {len(steps)}  [{kind}, {where}]")
        out(f"  {step.why}")
        out(f"  $ {shlex.join(step.argv)}")
        if step.stdin_prompt:
            out("  (the value comes from a hidden prompt, not from the command line)")
        if step.skip_if:
            out(f"  (skipped when this already exists; checked with: {shlex.join(step.skip_if)})")
        if step.use_if_exists:
            out(f"  (when it already exists, this runs instead: {shlex.join(step.use_if_exists[1])})")
        if step.optional:
            out("  (optional: a failure here is only a warning)")
        for path, text in step.files.items():
            out(f"  writes {path}")
            if show_files:
                out("  ----")
                out("\n".join("  | " + line for line in text.rstrip().splitlines()))
                out("  ----")


def in_repo(run: Runner) -> Runner:
    """Run every command from the repository root, whatever folder `make` was started in: the docker build uses relative paths."""

    def wrapped(argv, **kwargs):
        kwargs.setdefault("cwd", REPO)
        return run(argv, **kwargs)

    return wrapped


def list_jobs(cfg: Cfg, out=print) -> None:
    """The schedule, straight from deploy/gcp/app.toml, so what `make jobs` shows can never drift from what is deployed."""
    out(f"Jobs in {cfg.env} (schedules are India time, Asia/Kolkata):\n")
    out(f"  {'JOB':<22} {'RUNS':<24} {'COMMAND'}")
    for job in cfg.jobs.values():
        if job.envs is not None and cfg.env not in job.envs:
            continue
        when = job.schedule or ("with every-5-min" if job.bundled else "on demand")
        note = "" if job.enabled else "   (not built yet: switched off in app.toml)"
        out(f"  {job.key:<22} {when:<24} manage.py {' '.join([job.command, *job.args])}{note}")
    out("\nRun one now: make jobs-run ENV=production JOB=compute_matches")


def run_plan(
    steps: list[Step], run: Runner = subprocess.run, ask_secret: Callable[[str], str] = getpass.getpass, out=print
) -> None:
    for n, step in enumerate(steps, 1):
        out(f"\n[{n}/{len(steps)}] {step.why}")
        for path, text in step.files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        argv = step.argv
        if step.skip_if:
            probe = run(step.skip_if, capture_output=True, text=True)
            if probe.returncode == 0 and probe.stdout.strip():
                out("      already there, skipped")
                continue
        if step.use_if_exists:
            probe_argv, alt = step.use_if_exists
            if run(probe_argv, capture_output=True, text=True).returncode == 0:
                argv = alt
        out(f"  $ {shlex.join(argv)}")
        stdin = None
        if step.stdin_prompt:
            value = ask_secret(step.stdin_prompt + ": ")
            if not value:
                raise DeployError("Empty value; nothing was stored.")
            stdin = value
        if step.must_have_output:
            done = run(argv, capture_output=True, text=True)
            if done.returncode != 0 or not done.stdout.strip():
                raise DeployError(step.must_have_output)
            continue
        done = run(argv, input=stdin, text=True)
        if done.returncode != 0:
            if step.optional:
                out(f"      warning: step {n} failed (exit {done.returncode}); it is optional, carrying on")
                continue
            raise DeployError(
                f"Step {n} failed (exit code {done.returncode}). Nothing after it ran. Fix the cause shown above and run the same "
                "command again: every step is safe to repeat."
            )
    out("\nDone.")


def confirm(env: str, steps: list[Step], input_fn: Callable[[str], str] = input, out=print) -> bool:
    changing = sum(1 for s in steps if s.changes)
    out(f"\n{len(steps)} steps, {changing} of them change things in {env}. Nothing has been changed yet.")
    answer = input_fn(f'Type "{env}" to run them, anything else to stop: ')
    return answer.strip() == env


# ---- reading current state (read-only) -----------------------------------------------------------------------------------


def read_state(cfg: Cfg, run: Runner = subprocess.run, out=print) -> DeployState:
    p, r = _p(cfg), _r(cfg)
    out("Reading the current state (read-only):")
    num_cmd = gcloud("projects", "describe", cfg.project, "--format=value(projectNumber)")
    out(f"  $ {shlex.join(num_cmd)}")
    num = run(num_cmd, capture_output=True, text=True)
    if num.returncode != 0 or not num.stdout.strip():
        raise DeployError(
            f"Could not read project '{cfg.project}': {num.stderr.strip() or 'no output'}. Check `gcloud auth list` and project.id."
        )
    svc_cmd = gcloud("run", "services", "describe", cfg.service_name, *r, *p, "--format=json")
    out(f"  $ {shlex.join(svc_cmd)}")
    svc = run(svc_cmd, capture_output=True, text=True)
    serving = None
    if svc.returncode == 0:
        traffic = json.loads(svc.stdout).get("status", {}).get("traffic", [])
        full = [t for t in traffic if t.get("percent") == 100 and t.get("revisionName")]
        serving = full[0]["revisionName"] if full else None
    return DeployState(project_number=num.stdout.strip(), serving_revision=serving)


def read_revisions(cfg: Cfg, run: Runner = subprocess.run, out=print) -> tuple[list[Revision], str]:
    p, r = _p(cfg), _r(cfg)
    cmd = gcloud(
        "run",
        "revisions",
        "list",
        f"--service={cfg.service_name}",
        *r,
        *p,
        "--sort-by=~metadata.creationTimestamp",
        "--format=json",
    )
    out(f"  $ {shlex.join(cmd)}")
    done = run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        raise DeployError(f"Could not list revisions: {done.stderr.strip()}")
    revisions = [
        Revision(name=item["metadata"]["name"], image=item["spec"]["containers"][0]["image"]) for item in json.loads(done.stdout)
    ]
    cmd = gcloud("run", "services", "describe", cfg.service_name, *r, *p, "--format=json")
    out(f"  $ {shlex.join(cmd)}")
    svc = run(cmd, capture_output=True, text=True)
    if svc.returncode != 0:
        raise DeployError(f"Could not read the service: {svc.stderr.strip()}")
    traffic = json.loads(svc.stdout).get("status", {}).get("traffic", [])
    serving = [t["revisionName"] for t in traffic if t.get("percent") == 100 and t.get("revisionName")]
    if not serving:
        raise DeployError("No revision has 100% of traffic right now, so 'previous' is unclear. Use REVISION=<name>.")
    return revisions, serving[0]


def git_tag(run: Runner = subprocess.run, allow_dirty: bool = False) -> str:
    dirty = run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO).stdout.strip()
    if dirty and not allow_dirty:
        raise DeployError(
            "You have uncommitted changes. Commit them first: the image is named after the commit, so what runs is always what is in git."
        )
    sha = run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True, cwd=REPO).stdout.strip()
    if not sha:
        raise DeployError("Could not read the current git commit.")
    return sha


# ---- command line ---------------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None, run: Runner = subprocess.run, input_fn: Callable[[str], str] = input, out=print) -> int:
    ap = argparse.ArgumentParser(prog="gcp.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["setup", "deploy", "rollback", "secret", "jobs-run", "logs", "jobs", "monitoring"])
    ap.add_argument("--env", required=True, choices=ENVS)
    ap.add_argument("--dry-run", action="store_true", help="print the plan (and the files it writes) and stop; needs no gcloud")
    ap.add_argument("--name", help="secret: which secret, e.g. SECRET_KEY")
    ap.add_argument("--job", help="jobs-run / logs: job name, e.g. compute_matches")
    ap.add_argument("--revision", help="rollback: go to this revision instead of the previous one")
    ap.add_argument("--limit", type=int, default=50, help="logs: how many lines")
    ap.add_argument("--allow-dirty", action="store_true", help="deploy --dry-run only: tolerate uncommitted changes")
    args = ap.parse_args(argv)

    run = in_repo(run)
    try:
        cfg = load_config(args.env)
        if args.command == "jobs":
            list_jobs(cfg, out)
            return 0
        left = find_placeholders(cfg)
        if left and not args.dry_run:
            raise DeployError(
                f"deploy/gcp/{args.env}.toml still has values for you to fill in:\n  "
                + "\n  ".join(left)
                + "\nEdit the file, then run this again."
            )
        if left:
            out(
                f"Note: {len(left)} value(s) in deploy/gcp/{args.env}.toml are still <placeholders>; the plan below shows them as they are."
            )
        if not args.dry_run:
            for tool in ("gcloud", "docker") if args.command == "deploy" else ("gcloud",):
                if shutil.which(tool) is None:
                    hint = "yay -S google-cloud-cli" if tool == "gcloud" else "sudo pacman -S docker docker-buildx"
                    raise DeployError(f"'{tool}' is not installed. On Arch/Omarchy: {hint}")

        origins = [o for o in cfg.env_vars.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
        placeholder_state = DeployState(project_number="<PROJECT_NUMBER>", serving_revision=None)

        if args.command == "setup":
            steps = plan_setup(cfg)
        elif args.command == "deploy":
            tag = git_tag(run, allow_dirty=args.dry_run or args.allow_dirty)
            state = placeholder_state if args.dry_run else read_state(cfg, run, out)
            steps = plan_deploy(cfg, tag, state, origins)
            if state.serving_revision is None:
                out(
                    "This is a first deploy: there is no service yet, so there is no test address step."
                    if not args.dry_run
                    else "Dry run: shown as a first deploy. A later deploy also adds a 0%-traffic test step first."
                )
        elif args.command == "monitoring":
            state = placeholder_state if args.dry_run else read_state(cfg, run, out)
            steps = plan_monitoring(cfg, state.project_number, lenient=args.dry_run)
        elif args.command == "rollback":
            if args.dry_run:
                target = Revision(args.revision or "<previous-revision>", cfg.image("<its-tag>"))
                steps = plan_rollback(cfg, target, placeholder_state, origins)
            else:
                state = read_state(cfg, run, out)
                revisions, serving = read_revisions(cfg, run, out)
                target = choose_rollback(revisions, serving, args.revision)
                out(f"Serving now: {serving}   Going back to: {target.name}")
                steps = plan_rollback(cfg, target, state, origins)
        elif args.command == "secret":
            if not args.name:
                raise DeployError("Which secret? make secret ENV=production NAME=SECRET_KEY")
            steps = plan_secret(cfg, args.name)
        elif args.command == "jobs-run":
            if not args.job:
                raise DeployError("Which job? make jobs-run ENV=production JOB=compute_matches")
            steps = plan_jobs_run(cfg, args.job)
        else:
            steps = plan_logs(cfg, args.job, args.limit)

        print_plan(steps, out, show_files=args.dry_run)
        if args.dry_run:
            out("\nDry run: nothing was run.")
            return 0
        if all(not s.changes for s in steps):
            run_plan(steps, run, out=out)
            return 0
        if not confirm(args.env, steps, input_fn, out):
            out("Stopped. Nothing was changed.")
            return 1
        run_plan(steps, run, out=out)
        if args.command == "secret":
            out("Cloud Run reads secrets when an instance starts: run `make deploy` for the new value to take effect.")
        return 0
    except DeployError as exc:
        out(f"\nStopped: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
