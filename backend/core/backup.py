"""Nightly encrypted backup of the database (PRODUCTION.md §6, RUNBOOK.md "Restore from a backup").

What happens, in order (the `backup_db` job, 02:30 IST):
  1. count the rows of every table in `public` (before);
  2. `pg_dump --format=custom` of the `public` and `auth` schemas, piped straight into `age -r <public key>`, so a readable copy of the
     data never touches the disk. Only the PUBLIC key is in the cloud: a stolen job or bucket cannot open old backups. The private key
     is in your password manager and is used only by `make restore-drill` and by a real restore;
  3. count again (after), and write `<stamp>.counts.json`: table names and row counts, no data. The restore drill checks the restored
     database against it;
  4. upload both files to the private bucket (BACKUP_BUCKET). The bucket deletes them after 30 days (deploy/gcp/backup-lifecycle.json).
     With no bucket (a laptop) they go to backend/.backups/ instead.

Why a separate BACKUP_DATABASE_URL: pg_dump holds one connection open for the whole dump, which Supabase's transaction pooler (port
6543) cannot do. Use the SESSION pooler (port 5432 on the pooler host) or the direct address.

Storage files (post and message images) live in Supabase Storage, not in the database, and are not in this backup.
"""

import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
import structlog
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection

from core.monitoring import scrub_text

log = structlog.get_logger("backup")

SCHEMAS = (
    "public",
    "auth",
)  # `auth` holds the sign-in accounts (Supabase); without it a restored project would have members nobody can log in as
SKIP_TABLES = {"spatial_ref_sys"}  # PostGIS's own reference table, recreated by the extension
METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
UPLOAD_URL = "https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o"
UPLOAD_TIMEOUT_SECONDS = 600
UPLOAD_ATTEMPTS = 3
MIN_DUMP_BYTES = 1024  # a real dump of even an empty Circuit database is far larger; smaller means something went wrong


@dataclass
class BackupResult:
    dump_name: str
    counts_name: str
    bytes: int
    tables: int
    where: str  # "gs://bucket" or the local folder


def check_recipient(recipient: str) -> str:
    """An age PUBLIC key (age1...). Refuses a private key (AGE-SECRET-KEY-...) pasted here by mistake: that one must never reach the cloud."""
    value = recipient.strip()
    if "SECRET" in value.upper():
        raise CommandError(
            "BACKUP_AGE_RECIPIENT holds a PRIVATE key. Put only the public key (age1...) here; keep the private one offline."
        )
    if not re.fullmatch(r"age1[0-9a-z]{58}", value):
        raise CommandError(
            "BACKUP_AGE_RECIPIENT must be an age public key: age1 followed by 58 letters and digits (age-keygen prints it)."
        )
    return value


def pg_args(url: str) -> tuple[list[str], dict[str, str]]:
    """Connection flags and environment for pg_dump from a database URL. The password goes in PGPASSWORD, not on the command line,
    where any process on the machine could read it."""
    parts = urlparse(url)
    if parts.scheme not in ("postgres", "postgresql") or not parts.hostname:
        raise CommandError("BACKUP_DATABASE_URL must look like postgresql://user:password@host:5432/dbname")
    args = ["--host", parts.hostname, "--port", str(parts.port or 5432), "--username", unquote(parts.username or "postgres")]
    args += ["--dbname", (parts.path or "/postgres").lstrip("/") or "postgres"]
    env = {"PGPASSWORD": unquote(parts.password or "")}
    if parts.hostname not in ("localhost", "127.0.0.1", "::1", "db"):
        env["PGSSLMODE"] = "require"
    return args, env


def object_names(env: str, now: datetime | None = None) -> tuple[str, str]:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"{env}/{stamp}.dump.age", f"{env}/{stamp}.counts.json"


def existing_schemas() -> list[str]:
    with connection.cursor() as cur:
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = ANY(%s)", [list(SCHEMAS)])
        found = {row[0] for row in cur.fetchall()}
    return [s for s in SCHEMAS if s in found]  # a laptop database has no `auth` schema


def table_counts() -> dict[str, int]:
    """{table: rows} for every table of `public`. Exact counts: the database is small (free tier: 500 MB)."""
    quote = connection.ops.quote_name
    with connection.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
        names = sorted(r[0] for r in cur.fetchall() if r[0] not in SKIP_TABLES)
        counts = {}
        for name in names:
            cur.execute(f"SELECT count(*) FROM public.{quote(name)}")  # noqa: S608 (name comes from the catalog, quoted)
            counts[name] = cur.fetchone()[0]
    return counts


def build_commands(
    db_url: str, recipient: str, schemas: list[str], out_path: Path
) -> tuple[list[str], list[str], dict[str, str]]:
    """(pg_dump argv, age argv, environment for pg_dump)."""
    args, env = pg_args(db_url)
    dump = ["pg_dump", "--format=custom", "--no-owner", "--no-acl", *[f"--schema={s}" for s in schemas], *args]
    encrypt = ["age", "--recipient", recipient, "--output", str(out_path)]
    return dump, encrypt, env


def dump_encrypted(
    dump: list[str], encrypt: list[str], env: dict[str, str], popen: Callable[..., subprocess.Popen] = subprocess.Popen
) -> None:
    for tool in (dump[0], encrypt[0]):
        if shutil.which(tool) is None:
            raise CommandError(
                f"'{tool}' is not installed in this environment (the production image has both; on a laptop: pacman -S postgresql age)"
            )
    producer = popen(dump, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
    consumer = popen(encrypt, stdin=producer.stdout, stderr=subprocess.PIPE)
    if producer.stdout:
        producer.stdout.close()  # so pg_dump gets SIGPIPE if age dies
    age_err = consumer.communicate()[1]
    dump_err = producer.stderr.read() if producer.stderr else b""
    producer.wait()
    if producer.returncode != 0:
        raise CommandError(f"pg_dump failed (exit {producer.returncode}): {_first_line(dump_err)}")
    if consumer.returncode != 0:
        raise CommandError(f"age failed (exit {consumer.returncode}): {_first_line(age_err)}")


def _first_line(raw: bytes) -> str:
    text = raw.decode(errors="replace").strip().splitlines()
    return scrub_text(text[0])[:200] if text else "no message"


def _access_token(client: httpx.Client) -> str:
    resp = client.get(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"}, timeout=5)
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload(
    bucket: str,
    name: str,
    path: Path,
    content_type: str,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """One object into the bucket, with a timeout and retries with backoff. The token comes from the Cloud Run metadata server."""
    owns = client is None
    client = client or httpx.Client()
    try:
        last = "no attempt"
        for attempt in range(1, UPLOAD_ATTEMPTS + 1):
            try:
                token = _access_token(client)
                with path.open("rb") as handle:
                    resp = client.post(
                        UPLOAD_URL.format(bucket=bucket),
                        params={"uploadType": "media", "name": name},
                        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
                        content=handle,
                        timeout=UPLOAD_TIMEOUT_SECONDS,
                    )
                if resp.status_code < 300:
                    return
                last = f"HTTP {resp.status_code}"
            except httpx.HTTPError as exc:
                last = type(exc).__name__
            log.warning("backup.upload_retry", attempt=attempt, reason=last)
            if attempt < UPLOAD_ATTEMPTS:
                sleep(4**attempt)
        raise CommandError(f"Could not upload {name} to the backup bucket after {UPLOAD_ATTEMPTS} tries ({last})")
    finally:
        if owns:
            client.close()


def counts_document(
    env: str, dump_name: str, size: int, schemas: list[str], before: dict[str, int], after: dict[str, int]
) -> dict:
    return {
        "format": 1,
        "env": env,
        "release": getattr(settings, "RELEASE", ""),
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dump": dump_name,
        "bytes": size,
        "schemas": schemas,
        "tables": {t: {"before": before[t], "after": after.get(t, before[t])} for t in before},
    }


def backup(
    *,
    db_url: str | None = None,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    uploader: Callable[..., None] = upload,
    workdir: Path | None = None,
) -> BackupResult:
    db_url = db_url or settings.BACKUP_DATABASE_URL
    if not db_url:
        raise CommandError("BACKUP_DATABASE_URL is not set (the Supabase session-pooler or direct address; see RUNBOOK.md)")
    recipient = check_recipient(settings.BACKUP_AGE_RECIPIENT)
    dump_name, counts_name = object_names(settings.ENV)
    folder = workdir or Path(settings.BACKUP_DIR) / "tmp"
    folder.mkdir(parents=True, exist_ok=True)
    dump_path = folder / Path(dump_name).name
    counts_path = folder / Path(counts_name).name
    try:
        schemas = existing_schemas()
        before = table_counts()
        dump, encrypt, env = build_commands(db_url, recipient, schemas, dump_path)
        dump_encrypted(dump, encrypt, env, popen)
        size = dump_path.stat().st_size if dump_path.exists() else 0
        if size < MIN_DUMP_BYTES:
            raise CommandError(f"The encrypted dump is only {size} bytes: something went wrong, nothing was stored")
        after = table_counts()
        counts_path.write_text(json.dumps(counts_document(settings.ENV, dump_name, size, schemas, before, after), indent=2))
        if settings.BACKUP_BUCKET:
            uploader(settings.BACKUP_BUCKET, dump_name, dump_path, "application/octet-stream")
            uploader(settings.BACKUP_BUCKET, counts_name, counts_path, "application/json")
            where = f"gs://{settings.BACKUP_BUCKET}"
        else:  # a laptop: keep them next to the project, where `make restore-drill` looks
            target = Path(settings.BACKUP_DIR) / settings.ENV
            target.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dump_path), target / dump_path.name)
            shutil.move(str(counts_path), target / counts_path.name)
            where = str(target)
    finally:
        for leftover in (dump_path, counts_path):
            leftover.unlink(missing_ok=True)  # never leave a copy in the temporary folder
    log.info("backup.done", object=dump_name, bytes=size, tables=len(before))
    return BackupResult(dump_name, counts_name, size, len(before), where)
