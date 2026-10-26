"""scripts/check_api_freeze.py on throwaway git repositories, and the version line in FRONTEND_HANDOFF.md."""

import importlib.util
import json
import subprocess

import pytest
from django.conf import settings

REPO = settings.BASE_DIR.parent
spec = importlib.util.spec_from_file_location("check_api_freeze", REPO / "scripts/check_api_freeze.py")
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)


def _git(root, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=root, check=True, capture_output=True)


def _write(root, version, paths, handoff_extra=""):
    (root / "packages/api-client").mkdir(parents=True, exist_ok=True)
    (root / freeze.SPEC).write_text(json.dumps({"info": {"version": version}, "paths": paths}))
    (root / freeze.HANDOFF).write_text(f"# Handoff\n\n**API version:** {version} (frozen)\n{handoff_extra}")


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _write(tmp_path, "1.0.0", {"/a": {}})
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "switch", "-q", "-c", "work")
    return tmp_path


def _commit(root):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "change")


def test_no_change_passes(repo):
    assert freeze.check(repo, "main") == []


def test_changed_spec_without_a_bump_fails(repo):
    _write(repo, "1.0.0", {"/a": {}, "/b": {}}, "new /b")
    _commit(repo)
    assert any("info.version is still" in p for p in freeze.check(repo, "main"))


def test_changed_spec_without_a_handoff_change_fails(repo):
    (repo / freeze.SPEC).write_text(json.dumps({"info": {"version": "1.1.0"}, "paths": {"/a": {}, "/b": {}}}))
    (repo / freeze.HANDOFF).write_text("# Handoff\n\n**API version:** 1.1.0 (frozen)\n")
    (repo / freeze.HANDOFF).write_text((repo / freeze.HANDOFF).read_text().replace("1.1.0", "1.0.0"))  # handoff same as base
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "x")
    problems = freeze.check(repo, "main")
    assert any("did not" in p for p in problems) and any("must say" in p for p in problems)


def test_bump_plus_handoff_passes(repo):
    _write(repo, "1.1.0", {"/a": {}, "/b": {}}, "new /b")
    _commit(repo)
    assert freeze.check(repo, "main") == []


def test_a_lower_version_fails(repo):
    _write(repo, "0.9.0", {"/a": {}, "/b": {}}, "x")
    _commit(repo)
    assert any("info.version is still" in p for p in freeze.check(repo, "main"))


def test_version_only_change_needs_nothing_else(repo):
    _write(repo, "1.0.1", {"/a": {}})
    _commit(repo)
    assert freeze.check(repo, "main") == []


def test_the_real_handoff_states_the_real_version():
    spec_version = json.loads((REPO / freeze.SPEC).read_text())["info"]["version"]
    assert f"**API version:** {spec_version}" in (REPO / freeze.HANDOFF).read_text()
    assert freeze.check(REPO, "HEAD") == []
