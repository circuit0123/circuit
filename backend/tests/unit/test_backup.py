"""The nightly encrypted backup (core/backup.py, backup_db) and the restore drill (scripts/restore_drill.py).
No Postgres tools, no age, no network: subprocess and HTTP are replaced by fakes."""

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core import backup
from core.devguard import LOCAL_HOSTS
from core.models import JobRun

pytestmark = pytest.mark.django_db

REPO = Path(__file__).resolve().parents[3]
PUBLIC_KEY = "age1" + "q" * 58
URL = "postgresql://postgres.abc:p%40ss%2Fword@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, REPO / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


drill = _load("restore_drill", "scripts/restore_drill.py")


# ---- pieces ----------------------------------------------------------------------------------------------------------------


def test_only_an_age_public_key_is_accepted():
    assert backup.check_recipient(PUBLIC_KEY) == PUBLIC_KEY
    with pytest.raises(CommandError, match="PRIVATE"):
        backup.check_recipient("AGE-SECRET-KEY-1QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ")
    for bad in ("", "age1short", "ssh-ed25519 AAAA"):
        with pytest.raises(CommandError):
            backup.check_recipient(bad)


def test_the_password_goes_in_the_environment_never_on_the_command_line():
    args, env = backup.pg_args(URL)
    assert "p@ss/word" not in " ".join(args) and "ss" not in " ".join(args).replace("--username", "")
    assert env["PGPASSWORD"] == "p@ss/word" and env["PGSSLMODE"] == "require"
    assert args[:2] == ["--host", "aws-0-ap-south-1.pooler.supabase.com"] and "5432" in args
    _, local_env = backup.pg_args("postgresql://circuit:circuit@localhost:5432/circuit")
    assert "PGSSLMODE" not in local_env
    with pytest.raises(CommandError):
        backup.pg_args("mysql://x")


def test_object_names_sort_like_time_and_sit_under_the_environment():
    dump, counts = backup.object_names("production", datetime(2026, 10, 26, 21, 0, 5, tzinfo=UTC))
    assert dump == "production/20261026T210005Z.dump.age" and counts == "production/20261026T210005Z.counts.json"


def test_commands_encrypt_to_the_public_key_and_dump_both_schemas(tmp_path):
    dump, encrypt, env = backup.build_commands(URL, PUBLIC_KEY, ["public", "auth"], tmp_path / "x.age")
    assert dump[:3] == ["pg_dump", "--format=custom", "--no-owner"] and "--schema=auth" in dump and "--schema=public" in dump
    assert encrypt == ["age", "--recipient", PUBLIC_KEY, "--output", str(tmp_path / "x.age")]
    assert "PGPASSWORD" in env


def test_row_counts_cover_public_tables_and_hold_numbers_only():
    counts = backup.table_counts()
    assert "django_migrations" in counts and counts["django_migrations"] > 0
    assert "spatial_ref_sys" not in counts
    assert all(isinstance(n, int) for n in counts.values())
    assert backup.existing_schemas() == ["public"]  # a laptop database has no `auth` schema


# ---- the whole backup, with fakes ------------------------------------------------------------------------------------------


class FakeProc:
    def __init__(self, returncode=0, stderr=b"", on_start=None):
        self.returncode, self._stderr = returncode, stderr
        self.stdout = None
        self.stderr = type("S", (), {"read": lambda s: stderr})()
        self.on_start = on_start

    def communicate(self):
        if self.on_start:
            self.on_start()
        return b"", self._stderr

    def wait(self):
        return self.returncode


def popen_factory(dump_rc=0, age_rc=0, size=5000, dump_err=b"", age_err=b""):
    """Fake pg_dump then fake age; age 'writes' its --output file."""
    calls = []

    def popen(argv, **kw):
        calls.append(argv)
        if argv[0] == "pg_dump":
            return FakeProc(dump_rc, dump_err)
        out = Path(argv[argv.index("--output") + 1])
        return FakeProc(age_rc, age_err, on_start=lambda: out.write_bytes(b"x" * size))

    popen.calls = calls
    return popen


@pytest.fixture
def configured(settings, tmp_path, monkeypatch):
    settings.BACKUP_DATABASE_URL = URL
    settings.BACKUP_AGE_RECIPIENT = PUBLIC_KEY
    settings.BACKUP_BUCKET = "proj-circuit-production-backups"
    settings.BACKUP_DIR = tmp_path / "backups"
    settings.ENV = "production"
    monkeypatch.setattr(backup.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    return settings


class Uploads(list):
    def __call__(self, bucket, name, path, content_type):
        self.append((bucket, name, Path(path).stat().st_size, content_type))


def test_backup_uploads_the_encrypted_dump_and_a_counts_file_and_leaves_nothing_behind(configured, tmp_path):
    uploads = Uploads()
    result = backup.backup(popen=popen_factory(), uploader=uploads, workdir=tmp_path / "work")
    assert [u[0] for u in uploads] == ["proj-circuit-production-backups"] * 2
    assert uploads[0][1].endswith(".dump.age") and uploads[0][2] == 5000
    assert uploads[1][1].endswith(".counts.json") and uploads[1][3] == "application/json"
    assert result.bytes == 5000 and result.where == "gs://proj-circuit-production-backups"
    assert list((tmp_path / "work").iterdir()) == []  # no copy left in the temporary folder


def test_the_counts_file_has_table_names_and_numbers_and_no_data(configured, tmp_path):
    captured = {}

    def keep(bucket, name, path, content_type):
        if name.endswith(".json"):
            captured["doc"] = json.loads(Path(path).read_text())

    backup.backup(popen=popen_factory(), uploader=keep, workdir=tmp_path / "work")
    doc = captured["doc"]
    assert doc["env"] == "production" and doc["schemas"] == ["public"] and doc["bytes"] == 5000
    assert set(doc) == {"format", "env", "release", "taken_at", "dump", "bytes", "schemas", "tables"}
    assert all(set(v) == {"before", "after"} and isinstance(v["before"], int) for v in doc["tables"].values())


def test_without_a_bucket_the_files_land_in_the_local_backup_folder(configured, tmp_path):
    configured.BACKUP_BUCKET = ""
    configured.ENV = "dev"
    result = backup.backup(popen=popen_factory(), workdir=tmp_path / "work")
    files = sorted(p.name for p in (tmp_path / "backups" / "dev").iterdir())
    assert len(files) == 2 and files[0].endswith(".counts.json") and files[1].endswith(".dump.age")
    assert result.where == str(tmp_path / "backups" / "dev")


def test_a_failed_pg_dump_stores_nothing_and_does_not_leak_the_message_unscrubbed(configured, tmp_path):
    uploads = Uploads()
    err = b"pg_dump: error: connection to server failed for asha@example.com\nmore"
    with pytest.raises(CommandError, match="pg_dump failed") as exc:
        backup.backup(popen=popen_factory(dump_rc=1, dump_err=err), uploader=uploads, workdir=tmp_path / "work")
    assert "asha@example.com" not in str(exc.value) and not uploads
    assert list((tmp_path / "work").iterdir()) == []


def test_a_failed_age_stores_nothing(configured, tmp_path):
    uploads = Uploads()
    with pytest.raises(CommandError, match="age failed"):
        backup.backup(
            popen=popen_factory(age_rc=1, age_err=b"age: error: bad recipient"), uploader=uploads, workdir=tmp_path / "work"
        )
    assert not uploads


def test_a_tiny_dump_is_refused(configured, tmp_path):
    uploads = Uploads()
    with pytest.raises(CommandError, match="only 10 bytes"):
        backup.backup(popen=popen_factory(size=10), uploader=uploads, workdir=tmp_path / "work")
    assert not uploads


def test_missing_settings_stop_with_a_clear_message(configured, tmp_path):
    configured.BACKUP_DATABASE_URL = ""
    with pytest.raises(CommandError, match="BACKUP_DATABASE_URL"):
        backup.backup(popen=popen_factory(), workdir=tmp_path)
    configured.BACKUP_DATABASE_URL = URL
    configured.BACKUP_AGE_RECIPIENT = ""
    with pytest.raises(CommandError, match="age public key"):
        backup.backup(popen=popen_factory(), workdir=tmp_path)


def test_missing_tools_are_named(configured, tmp_path, monkeypatch):
    monkeypatch.setattr(backup.shutil, "which", lambda tool: None)
    with pytest.raises(CommandError, match="'pg_dump' is not installed"):
        backup.backup(popen=popen_factory(), workdir=tmp_path)


# ---- the upload ------------------------------------------------------------------------------------------------------------


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_upload_sends_the_file_with_a_metadata_token(tmp_path):
    f = tmp_path / "a.age"
    f.write_bytes(b"cipher")
    seen = []

    def handler(request):
        seen.append(request)
        if "metadata.google.internal" in str(request.url):
            assert request.headers["Metadata-Flavor"] == "Google"
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(200, json={})

    backup.upload("b", "production/x.dump.age", f, "application/octet-stream", client=_client(handler), sleep=lambda s: None)
    post = seen[-1]
    assert (
        post.url.params["name"] == "production/x.dump.age"
        and post.headers["Authorization"] == "Bearer tok"
        and post.content == b"cipher"
    )


def test_upload_retries_with_backoff_then_gives_up(tmp_path):
    f = tmp_path / "a.age"
    f.write_bytes(b"cipher")
    sleeps = []

    def handler(request):
        if "metadata" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(503)

    with pytest.raises(CommandError, match="after 3 tries"):
        backup.upload("b", "n", f, "x", client=_client(handler), sleep=sleeps.append)
    assert sleeps == [4, 16]


def test_upload_recovers_after_one_failure(tmp_path):
    f = tmp_path / "a.age"
    f.write_bytes(b"cipher")
    state = {"n": 0}

    def handler(request):
        if "metadata" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok"})
        state["n"] += 1
        return httpx.Response(500 if state["n"] == 1 else 200, json={})

    backup.upload("b", "n", f, "x", client=_client(handler), sleep=lambda s: None)
    assert state["n"] == 2


# ---- the job ---------------------------------------------------------------------------------------------------------------


def test_backup_db_is_a_job_that_records_its_result(monkeypatch, capsys, settings):
    settings.BACKUP_DATABASE_URL = URL
    monkeypatch.setattr(backup, "backup", lambda: backup.BackupResult("d", "c", 12_300_000, 87, "gs://b"))
    call_command("backup_db")
    assert "12.3 MB, 87 tables" in capsys.readouterr().out
    row = JobRun.objects.get(name="backup_db")
    assert row.last_status == "ok" and row.last_success_at


def test_a_failed_backup_is_a_failed_job(monkeypatch, settings):
    settings.BACKUP_DATABASE_URL = URL
    def boom():
        raise CommandError("pg_dump failed (exit 1): no message")

    monkeypatch.setattr(backup, "backup", boom)
    with pytest.raises(CommandError):
        call_command("backup_db")
    row = JobRun.objects.get(name="backup_db")
    assert row.last_status == "failed" and "pg_dump failed" in row.last_error


def test_backup_db_without_a_database_address_skips_and_exits_zero(monkeypatch, capsys, settings):
    settings.BACKUP_DATABASE_URL = ""
    monkeypatch.setattr(backup, "backup", lambda: pytest.fail("must not try to back up"))
    call_command("backup_db")  # no exception = exit code 0
    assert "skipped: not configured" in capsys.readouterr().out
    row = JobRun.objects.get(name="backup_db")
    assert row.last_status == "skipped" and not row.last_error


# ---- the restore drill -----------------------------------------------------------------------------------------------------


def test_the_drill_lists_exactly_the_hosts_the_backend_treats_as_local():
    assert drill.LOCAL_HOSTS - {"restore-db"} == LOCAL_HOSTS
    for host in ("db.abc.supabase.co", "aws-0-ap-south-1.pooler.supabase.com", "10.0.0.5"):
        with pytest.raises(drill.DrillError, match="only ever restores into a database on this computer"):
            drill.require_local(host)
    drill.require_local(drill.SCRATCH_HOST)
    assert drill.SCRATCH_PORT == 5433  # not the dev database's 5432


def test_the_drill_never_reads_the_real_database_settings():
    source = (REPO / "scripts" / "restore_drill.py").read_text()
    assert "environ" in source and 'environ.get("AGE_KEY_FILE"' in source
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(("#", '"""')))
    assert 'environ.get("DATABASE_URL"' not in code and 'environ["DATABASE_URL"]' not in code
    assert "BACKUP_DATABASE_URL" in source.split('"""')[1]  # only in the sentence that says it never reads it


def test_newest_dump_is_picked_by_its_timestamp():
    names = [
        "20261024T210000Z.dump.age",
        "20261026T210000Z.dump.age",
        "20261025T210000Z.counts.json",
        "20261025T210000Z.dump.age",
    ]
    assert drill.newest(names) == "20261026T210000Z.dump.age"
    with pytest.raises(drill.DrillError):
        drill.newest(["a.counts.json"])


COUNTS = {
    "tables": {
        "members": {"before": 100, "after": 104},
        "posts": {"before": 0, "after": 0},
        "notifications": {"before": 1000, "after": 1000},
    }
}


def test_counts_pass_inside_the_window_and_fail_outside_it():
    ok = drill.check_counts(COUNTS, {"members": 102, "posts": 0, "notifications": 1010})
    assert all(r[1] for r in ok)
    bad = {r[0]: r for r in drill.check_counts(COUNTS, {"members": 90, "notifications": 1000})}
    assert not bad["members"][1] and "expected 100-104" in bad["members"][2]
    assert not bad["posts"][1] and "missing" in bad["posts"][2]
    assert bad["notifications"][1]


def test_an_empty_table_must_stay_empty():
    results = {r[0]: r[1] for r in drill.check_counts(COUNTS, {"members": 100, "posts": 50, "notifications": 1000})}
    assert not results["posts"] and results["members"]


def test_extension_schema_is_detected_from_the_dump():
    assert drill.dump_expects_extensions_schema(
        "CREATE TABLE public.x (loc extensions.geometry(Point,4326), v extensions.vector(384))"
    )
    assert not drill.dump_expects_extensions_schema("CREATE TABLE public.x (loc public.geometry(Point,4326))")


def test_the_drill_end_to_end_with_fakes(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "dev"
    folder.mkdir()
    (folder / "20261026T210000Z.dump.age").write_bytes(b"cipher")
    (folder / "20261026T210000Z.counts.json").write_text(json.dumps(COUNTS))
    key = tmp_path / "backup.key"
    key.write_text("AGE-SECRET-KEY-FAKE")
    monkeypatch.setattr(drill.shutil, "which", lambda t: f"/usr/bin/{t}")
    seen = []

    def run(argv, **kw):
        seen.append(argv)
        text = " ".join(argv)
        if argv[0] == "age":
            Path(argv[argv.index("--output") + 1]).write_bytes(b"PGDMP")
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:2] == ["docker", "cp"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        out = ""
        if " ps -q" in text:
            out = "cid123\n"
        elif "pg_restore --schema-only" in text:
            out = "CREATE TABLE public.members (id int, loc extensions.geometry);"
        elif "information_schema.tables" in text:
            out = "members\nnotifications\nposts\nspatial_ref_sys\n"
        elif "count(*)" in text:
            out = {"members": "101", "notifications": "1000", "posts": "0"}[text.split('public."')[1].split('"')[0]]
        return subprocess.CompletedProcess(
            argv, 0, out, 'pg_restore: error: role "anon" does not exist\n' if "pg_restore -U" in text else ""
        )

    code = drill.main(["--key-file", str(key)], run=run, out=print, local_dir=folder)
    output = capsys.readouterr().out
    assert code == 0 and "OK: 3 of 3 tables match" in output and "reported 1 error" in output
    flat = [" ".join(a) for a in seen]
    assert any("CREATE SCHEMA IF NOT EXISTS extensions" in c for c in flat)  # the dump used extensions.geometry
    assert any(c.endswith("rm -sfv restore-db") for c in flat)  # the scratch database is always removed
    assert not any("DATABASE_URL" in c for c in flat)


def test_the_drill_fails_loudly_when_a_table_is_short(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "dev"
    folder.mkdir()
    (folder / "20261026T210000Z.dump.age").write_bytes(b"cipher")
    (folder / "20261026T210000Z.counts.json").write_text(json.dumps(COUNTS))
    key = tmp_path / "backup.key"
    key.write_text("x")
    monkeypatch.setattr(drill.shutil, "which", lambda t: f"/usr/bin/{t}")

    def run(argv, **kw):
        text = " ".join(argv)
        if argv[0] == "age":
            Path(argv[argv.index("--output") + 1]).write_bytes(b"PGDMP")
            return subprocess.CompletedProcess(argv, 0, "", "")
        out = "members\n" if "information_schema.tables" in text else ("7" if "count(*)" in text else "cid\n")
        return subprocess.CompletedProcess(argv, 0, out, "")

    assert drill.main(["--key-file", str(key)], run=run, local_dir=folder) == 1
    assert "FAIL  notifications" in capsys.readouterr().out


def test_the_drill_needs_a_key_and_a_backup(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AGE_KEY_FILE", raising=False)
    assert drill.main([], local_dir=tmp_path) == 1
    assert "AGE_KEY_FILE" in capsys.readouterr().out
    assert drill.main(["--key-file", "k"], local_dir=tmp_path / "nope") == 1
    assert "make backup-now" in capsys.readouterr().out


# ---- deploy plan -----------------------------------------------------------------------------------------------------------


def test_setup_creates_a_private_bucket_that_the_api_can_only_add_to():
    gcp = _load("gcp_for_backup", "scripts/gcp.py")
    import tempfile

    from tests.unit.test_deploy_config import filled

    with tempfile.TemporaryDirectory() as tmp:
        cfg = gcp.load_config("production", filled("production", Path(tmp)))
    steps = gcp.plan_setup(cfg)
    flat = [" ".join(s.argv) for s in steps]
    bucket = f"gs://{cfg.backup_bucket}"
    assert any(
        "buckets create" in c and bucket in c and "--public-access-prevention" in c and "--uniform-bucket-level-access" in c
        for c in flat
    )
    assert any("--lifecycle-file" in c and "backup-lifecycle.json" in c for c in flat)
    assert any("add-iam-policy-binding" in c and bucket in c and "roles/storage.objectCreator" in c for c in flat)
    assert not any("storage.objectAdmin" in c or "storage.admin" in c or "objectViewer" in c for c in flat)
    rule = json.loads((REPO / "deploy/gcp/backup-lifecycle.json").read_text())["rule"]
    assert rule == [{"action": {"type": "Delete"}, "condition": {"age": 30}}]


def test_only_production_backs_up_and_the_job_is_nightly():
    gcp = _load("gcp_for_backup2", "scripts/gcp.py")
    import tempfile

    from tests.unit.test_deploy_config import filled

    with tempfile.TemporaryDirectory() as tmp:
        prod = gcp.load_config("production", filled("production", Path(tmp) / "p"))
        staging = gcp.load_config("staging", filled("staging", Path(tmp) / "s"))
    assert prod.has_backups and not staging.has_backups
    assert prod.jobs["backup-db"].schedule == "30 2 * * *" and gcp.job_intervals(prod)["backup_db"] == 1440
    env = {e["name"]: e.get("value") for e in gcp.container_env(prod, "1")}
    assert env["BACKUP_BUCKET"] == prod.backup_bucket and "BACKUP_BUCKET" not in {
        e["name"] for e in gcp.container_env(staging, "1")
    }
    # beta: not mounted, because Cloud Run refuses an empty secret. The job skips until it is added to production.toml `secrets`
    assert "BACKUP_DATABASE_URL" not in prod.secrets
