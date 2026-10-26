"""Guard rails on the production image recipe (docker/backend/Dockerfile, circuit/gunicorn.py). No Docker needed."""

import importlib.util
import re

from django.conf import settings

REPO = settings.BASE_DIR.parent
DOCKERFILE = (REPO / "docker/backend/Dockerfile").read_text()


def _instructions(name: str) -> list[str]:
    return [line for line in DOCKERFILE.splitlines() if line.startswith(name + " ")]


def test_image_runs_as_a_non_root_user():
    users = _instructions("USER")
    assert users and users[-1].split()[1] not in ("root", "0")


def test_image_starts_gunicorn_on_the_cloud_run_port_and_never_migrates():
    cmd = _instructions("CMD")[-1]
    assert "gunicorn" in cmd and "circuit/gunicorn.py" in cmd
    assert "migrate" not in cmd  # migrations are their own Cloud Run Job, run before a revision gets traffic
    gunicorn_conf = (REPO / "backend/circuit/gunicorn.py").read_text()
    assert "$PORT" in gunicorn_conf or "environ.get('PORT'" in gunicorn_conf or 'environ.get("PORT"' in gunicorn_conf
    assert "migrate" not in gunicorn_conf


def test_image_has_a_healthcheck_and_is_multi_stage():
    assert _instructions("HEALTHCHECK")
    assert len(_instructions("FROM")) == 2


def test_no_secret_files_are_copied_into_the_image():
    copies = " ".join(_instructions("COPY"))
    assert ".env" not in copies
    ignore = (REPO / ".dockerignore").read_text().splitlines()
    assert ".env" in ignore and ".env.*" in ignore and "!.env.example" in ignore


def test_train_ranker_data_is_in_the_build_context():
    # train_ranker and eval_matching read tests/eval/pairs.json at run time, so .dockerignore must let it through.
    ignore = (REPO / ".dockerignore").read_text().splitlines()
    assert "!backend/tests/eval" in ignore


def test_gunicorn_workers_times_threads_matches_the_default_cloud_run_concurrency(monkeypatch):
    for var in ("WEB_CONCURRENCY", "GUNICORN_THREADS", "PORT"):
        monkeypatch.delenv(var, raising=False)
    spec = importlib.util.spec_from_file_location("gunicorn_conf", REPO / "backend/circuit/gunicorn.py")
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
    assert conf.worker_class == "gthread"
    assert conf.workers * conf.threads == 8
    assert conf.bind.endswith(":8080")
    assert conf.graceful_timeout < 10  # Cloud Run kills the container 10 s after SIGTERM


def test_whitenoise_serves_admin_static_files_and_sits_right_after_security_middleware():
    mw = settings.MIDDLEWARE
    assert mw.index("whitenoise.middleware.WhiteNoiseMiddleware") == mw.index("django.middleware.security.SecurityMiddleware") + 1
    assert "django.contrib.staticfiles" in settings.INSTALLED_APPS


def test_dockerfile_does_not_hard_code_a_domain():
    assert not re.search(
        r"https?://(?!app\.invalid|www\.invalid|api\.invalid|localhost|127\.0\.0\.1)[a-z0-9.-]+\.(com|in|app|dev)\b", DOCKERFILE
    )


def test_image_can_make_the_encrypted_backup():
    runtime = DOCKERFILE.split("FROM python:3.12-slim-trixie\n", 2)[-1]
    assert "postgresql-client-17" in runtime and re.search(r"\bage\b", runtime)  # pg_dump and age, in the stage that ships
