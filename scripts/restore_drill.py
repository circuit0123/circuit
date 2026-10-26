#!/usr/bin/env python3
"""Restore the newest backup into a throwaway LOCAL database and check it (RUNBOOK.md "Restore from a backup").

    make restore-drill                 the newest backup in backend/.backups/dev/      (made by `make backup-now`)
    make restore-drill ENV=production  the newest backup in the production bucket     (read with YOUR gcloud login)

You need the PRIVATE key that matches BACKUP_AGE_RECIPIENT: AGE_KEY_FILE=/path/to/backup.key (kept offline, e.g. in your password manager).

What it does, so it is never a black box:
  1. finds the newest `<stamp>.dump.age` and its `<stamp>.counts.json`;
  2. decrypts it on this computer with `age`;
  3. starts the `restore-db` service from docker-compose.yml (profile `drill`): an empty Postgres with PostGIS and pgvector on
     localhost:5433, no volume, so it vanishes when stopped;
  4. restores into it with the pg_restore that ships INSIDE that container;
  5. counts every table and compares with the counts file, then prints PASS or FAIL per table;
  6. stops and removes the scratch database and the decrypted copy, pass or fail.

It NEVER reads DATABASE_URL or BACKUP_DATABASE_URL, and it refuses to talk to any database that is not on this computer.
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "restore-db", "host.docker.internal"}  # = backend/core/devguard.py + the scratch service
SCRATCH_HOST, SCRATCH_PORT, SCRATCH_USER, SCRATCH_DB = "localhost", 5433, "circuit", "restore"
SERVICE = "restore-db"
SLACK_ROWS, SLACK_SHARE = 5, 0.02  # rows can change while the dump runs; see check_counts

Runner = Callable[..., subprocess.CompletedProcess]


class DrillError(Exception):
    """Something the person can fix; printed without a traceback."""


def require_local(host: str) -> None:
    if host not in LOCAL_HOSTS:
        raise DrillError(f"Refusing to restore into '{host}': the drill only ever restores into a database on this computer.")


def newest(names: list[str]) -> str:
    """The newest `<stamp>.dump.age` of a list of file names. The stamp (20261026T210000Z) sorts like time."""
    dumps = sorted(n for n in names if n.endswith(".dump.age"))
    if not dumps:
        raise DrillError("No backup found (a file ending in .dump.age). Run `make backup-now` first, or check the bucket.")
    return dumps[-1]


def check_counts(counts: dict, restored: dict[str, int]) -> list[tuple[str, bool, str]]:
    """[(table, ok, detail)] for every table in the counts file. A table passes when the restored count lies between the count taken
    just before the dump and the one taken just after it (rows are added and removed while it runs), give or take a small slack."""
    out = []
    for table, seen in sorted(counts["tables"].items()):
        low, high = sorted((seen["before"], seen["after"]))
        slack = max(SLACK_ROWS, int(high * SLACK_SHARE))
        got = restored.get(table)
        if got is None:
            out.append((table, False, f"missing after the restore (expected about {high})"))
        elif low - slack <= got <= high + slack:
            out.append((table, True, f"{got} rows"))
        else:
            out.append((table, False, f"{got} rows, expected {low}" + (f"-{high}" if high != low else "")))
    extra = sorted(set(restored) - set(counts["tables"]))
    for table in extra:
        out.append((table, True, f"{restored[table]} rows (not in the counts file; a table added after the backup is impossible, so check)"))
    return out


def dump_expects_extensions_schema(schema_sql: str) -> bool:
    """Supabase installs PostGIS and pgvector in the `extensions` schema; a laptop installs them in `public`. The dump names the types with
    their schema, so look at which one it uses."""
    return bool(re.search(r"\bextensions\.(geometry|geography|vector)\b", schema_sql))


class Drill:
    def __init__(self, run: Runner = subprocess.run, out: Callable[[str], None] = print):
        self.run, self.out = run, out
        self.compose = ["docker", "compose", "--profile", "drill"]

    def sh(self, argv: list[str], *, check: bool = True, capture: bool = False, **kw) -> subprocess.CompletedProcess:
        self.out(f"  $ {shlex.join(argv)}")
        done = self.run(argv, cwd=REPO, text=True, capture_output=capture, **kw)
        if check and done.returncode != 0:
            raise DrillError(f"Command failed (exit {done.returncode}): {shlex.join(argv[:4])} ...")
        return done

    def psql(self, sql: str, db: str = SCRATCH_DB, *, check: bool = True) -> str:
        argv = [*self.compose, "exec", "-T", SERVICE, "psql", "-U", SCRATCH_USER, "-d", db, "-At", "-v", "ON_ERROR_STOP=1", "-c", sql]
        return self.sh(argv, check=check, capture=True).stdout.strip()

    def start(self) -> None:
        require_local(SCRATCH_HOST)
        self.sh([*self.compose, "up", "-d", "--wait", SERVICE])
        self.psql(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"', "postgres")
        self.psql(f'CREATE DATABASE "{SCRATCH_DB}"', "postgres")

    def stop(self) -> None:
        self.sh([*self.compose, "rm", "-sfv", SERVICE], check=False)

    def prepare(self, extensions_schema: bool) -> None:
        """What Supabase provides and a plain Postgres does not: the roles the dump refers to and the extensions."""
        for role in ("anon", "authenticated", "service_role"):
            self.psql(f"DO $$ BEGIN CREATE ROLE {role} NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$", check=False)
        schema = "extensions" if extensions_schema else "public"
        if extensions_schema:
            self.psql("CREATE SCHEMA IF NOT EXISTS extensions")
        for ext in ("postgis", "vector"):
            self.psql(f"CREATE EXTENSION IF NOT EXISTS {ext} SCHEMA {schema}")
        self.psql(f"ALTER DATABASE {SCRATCH_DB} SET search_path TO public, extensions")

    def restore(self, dump: Path) -> int:
        """pg_restore of the `public` schema; returns how many errors it reported (it keeps going). The row counts decide pass or fail."""
        remote = "/tmp/restore.dump"
        cid = self.sh([*self.compose, "ps", "-q", SERVICE], capture=True).stdout.strip()
        self.sh(["docker", "cp", str(dump), f"{cid}:{remote}"])
        schema_sql = self.sh(
            [*self.compose, "exec", "-T", SERVICE, "pg_restore", "--schema-only", "--schema=public", "-f", "-", remote], capture=True
        ).stdout
        self.prepare(dump_expects_extensions_schema(schema_sql))
        done = self.sh(
            [
                *self.compose, "exec", "-T", SERVICE, "pg_restore", "-U", SCRATCH_USER, "-d", SCRATCH_DB,
                "--schema=public", "--no-owner", "--no-acl", remote,
            ],
            check=False,
            capture=True,
        )  # fmt: skip
        errors = len([line for line in (done.stderr or "").splitlines() if line.startswith("pg_restore: error")])
        if done.returncode not in (0, 1):
            raise DrillError(f"pg_restore stopped (exit {done.returncode}): {(done.stderr or '').strip().splitlines()[:1]}")
        return errors

    def counts(self) -> dict[str, int]:
        names = self.psql(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1"
        ).splitlines()
        result = {}
        for name in names:
            if name == "spatial_ref_sys":
                continue
            result[name] = int(self.psql(f'SELECT count(*) FROM public."{name}"'))
        return result


# ---- finding and decrypting the backup ------------------------------------------------------------------------------------


def fetch_local(folder: Path) -> tuple[Path, Path]:
    if not folder.is_dir():
        raise DrillError(f"{folder} does not exist. Run `make backup-now` first.")
    dump = folder / newest([p.name for p in folder.iterdir()])
    counts = dump.with_name(dump.name.removesuffix(".dump.age") + ".counts.json")
    if not counts.is_file():
        raise DrillError(f"{counts.name} is missing next to the dump.")
    return dump, counts


def fetch_bucket(bucket: str, env: str, into: Path, run: Runner = subprocess.run, out=print) -> tuple[Path, Path]:
    """Read-only against Google Cloud: list, then copy two files. Uses your own gcloud login."""
    if shutil.which("gcloud") is None:
        raise DrillError("gcloud is not installed (yay -S google-cloud-cli) or you are not logged in (gcloud auth login).")
    listing = run(["gcloud", "storage", "ls", f"gs://{bucket}/{env}/"], capture_output=True, text=True)
    if listing.returncode != 0:
        raise DrillError(f"Could not list gs://{bucket}/{env}/: {listing.stderr.strip().splitlines()[:1]}. Your login needs read access to the bucket.")
    latest = newest([line.rsplit("/", 1)[-1] for line in listing.stdout.splitlines()])
    stem = latest.removesuffix(".dump.age")
    for name in (latest, stem + ".counts.json"):
        out(f"  $ gcloud storage cp gs://{bucket}/{env}/{name} {into}/")
        done = run(["gcloud", "storage", "cp", f"gs://{bucket}/{env}/{name}", str(into) + "/"], capture_output=True, text=True)
        if done.returncode != 0:
            raise DrillError(f"Could not download {name}: {done.stderr.strip().splitlines()[:1]}")
    return into / latest, into / (stem + ".counts.json")


def decrypt(dump: Path, key_file: Path, into: Path, run: Runner = subprocess.run) -> Path:
    if shutil.which("age") is None:
        raise DrillError("'age' is not installed (sudo pacman -S age).")
    if not key_file.is_file():
        raise DrillError(f"AGE_KEY_FILE={key_file} does not exist. It is the private key you made with `age-keygen -o backup.key`.")
    target = into / dump.name.removesuffix(".age")
    done = run(["age", "--decrypt", "--identity", str(key_file), "--output", str(target), str(dump)], capture_output=True, text=True)
    if done.returncode != 0:
        raise DrillError("age could not decrypt the backup: wrong key file, or the file is damaged.")
    return target


def main(
    argv: list[str] | None = None, run: Runner = subprocess.run, out: Callable[[str], None] = print, local_dir: Path | None = None
) -> int:
    ap = argparse.ArgumentParser(prog="restore_drill.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--env", default="", help="production | staging | demo: read the newest backup from that bucket (default: backend/.backups/dev)")
    ap.add_argument("--key-file", default="", help="the PRIVATE age key (or set AGE_KEY_FILE)")
    ap.add_argument("--keep", action="store_true", help="leave the scratch database running afterwards (psql -h localhost -p 5433 -U circuit restore)")
    args = ap.parse_args(argv)
    import os

    drill = Drill(run, out)
    started = False
    try:
        key = args.key_file or os.environ.get("AGE_KEY_FILE", "")
        if not key:
            raise DrillError("Which private key? AGE_KEY_FILE=/path/to/backup.key make restore-drill")
        with tempfile.TemporaryDirectory(prefix="circuit-drill-") as tmp:
            folder = Path(tmp)
            if args.env:
                import gcp

                cfg = gcp.load_config(args.env)
                out(f"Newest backup in gs://{cfg.backup_bucket}/{args.env}/ ...")
                dump, counts_path = fetch_bucket(cfg.backup_bucket, args.env, folder, run, out)
            else:
                dump, counts_path = fetch_local(local_dir or REPO / "backend" / ".backups" / "dev")
            out(f"Backup: {dump.name}")
            counts = json.loads(counts_path.read_text())
            plain = decrypt(dump, Path(key).expanduser(), folder, run)
            started = True
            drill.start()
            errors = drill.restore(plain)
            restored = drill.counts()
        results = check_counts(counts, restored)
        failed = [r for r in results if not r[1]]
        out("")
        for table, ok, detail in results:
            out(f"  {'PASS' if ok else 'FAIL'}  {table:<40} {detail}")
        out(f"\npg_restore reported {errors} error(s) (some are normal: Supabase-only roles and extensions).")
        out(f"{'OK' if not failed else 'FAILED'}: {len(results) - len(failed)} of {len(results)} tables match the counts taken at backup time.")
        return 0 if not failed else 1
    except DrillError as exc:
        out(f"\nStopped: {exc}")
        return 1
    finally:
        if started and not args.keep:
            drill.stop()


if __name__ == "__main__":
    sys.exit(main())
