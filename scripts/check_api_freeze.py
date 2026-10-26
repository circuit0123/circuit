#!/usr/bin/env python3
"""Fail when the API description changed without a version bump and a FRONTEND_HANDOFF.md update. Standard library only.

    python3 scripts/check_api_freeze.py --base origin/main      (make api-freeze)

The API is frozen at the version in packages/api-client/openapi.json (`info.version`). Any other change to that file, compared
with the base commit, needs (1) a higher `info.version` and (2) a change to FRONTEND_HANDOFF.md in the same branch, because the
handoff is what the frontend reads. Also checks the handoff's first "API version" line matches the file.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SPEC = "packages/api-client/openapi.json"
HANDOFF = "FRONTEND_HANDOFF.md"


def git(root: Path, *args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v.split("-")[0])[:3])


def without_version(spec: dict) -> dict:
    copy = json.loads(json.dumps(spec))
    copy.get("info", {}).pop("version", None)
    return copy


def check(root: Path, base: str) -> list[str]:
    problems: list[str] = []
    now = json.loads((root / SPEC).read_text())
    handoff = (root / HANDOFF).read_text()
    line = re.search(r"^\*\*API version:\*\*\s*(\S+)", handoff, flags=re.MULTILINE)
    if not line or line.group(1).rstrip(".,") != now["info"]["version"]:
        problems.append(f"{HANDOFF} must say '**API version:** {now['info']['version']}' near the top (it matches info.version).")
    old_text = git(root, "show", f"{base}:{SPEC}")
    if old_text is None:
        return problems  # nothing to compare with (new branch without the base): nothing frozen yet
    old = json.loads(old_text)
    if without_version(old) == without_version(now):
        return problems
    if version_tuple(now["info"]["version"]) <= version_tuple(old["info"]["version"]):
        problems.append(
            f"openapi.json changed but info.version is still {now['info']['version']} (base: {old['info']['version']}). "
            "Raise it in backend/circuit/api.py (new endpoint or field: minor, breaking change: major), then run `make api-client`."
        )
    committed = (git(root, "diff", "--name-only", f"{base}...HEAD", "--", HANDOFF) or "").strip()
    uncommitted = (git(root, "status", "--porcelain", "--", HANDOFF) or "").strip()
    if not (committed or uncommitted):
        problems.append(f"openapi.json changed but {HANDOFF} did not. Describe the change there (section 3, 'What changed').")
    return problems


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="origin/main")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = p.parse_args()
    problems = check(Path(args.root), args.base)
    for msg in problems:
        print(f"FAIL  {msg}")
    print("OK: the API description is in step with its version and the handoff" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
