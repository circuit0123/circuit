"""COMMANDS.md and the Makefile agree: a command a human runs is a `make` target, and every target is explained."""

import re

from django.conf import settings

REPO = settings.BASE_DIR.parent
MAKEFILE = (REPO / "Makefile").read_text()
COMMANDS = (REPO / "COMMANDS.md").read_text()
TARGETS = set(re.findall(r"^([a-zA-Z0-9_-]+):.*## ", MAKEFILE, flags=re.MULTILINE))


def test_every_cloud_target_is_documented_with_when_and_what_success_looks_like():
    section = COMMANDS[COMMANDS.index("## 9. Deploy to Google Cloud") :]
    for target in ("gcp-setup", "secret", "deploy", "smoke", "rollback", "jobs-run", "logs", "jobs"):
        assert target in TARGETS, f"make {target} is missing"
        assert re.search(rf"`make {target}[ `]", section), f"COMMANDS.md section 9 does not explain make {target}"
    assert "What success looks like" in section


def test_every_target_in_the_makefile_is_mentioned_in_commands_md():
    undocumented = sorted(t for t in TARGETS if t != "help" and not re.search(rf"make {re.escape(t)}\b", COMMANDS))
    assert not undocumented, f"add to COMMANDS.md: {undocumented}"


def test_commands_md_does_not_promise_targets_that_do_not_exist():
    mentioned = set(re.findall(r"`make ([a-z][a-z0-9-]*)", COMMANDS))
    assert mentioned <= TARGETS, f"COMMANDS.md mentions targets the Makefile does not have: {sorted(mentioned - TARGETS)}"


def test_no_target_still_says_it_is_not_built_for_stage_5():
    assert "until Stage 5" not in MAKEFILE and "until Stage 5" not in COMMANDS


def test_there_is_no_cloud_command_in_make_check():
    check_line = re.search(r"^check:.*$", MAKEFILE, flags=re.MULTILINE).group(0)
    assert not any(word in check_line for word in ("deploy", "gcp", "secret", "rollback", "jobs-run"))
