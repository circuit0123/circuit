"""RUNBOOK.md has the sections that alerts and docs point to, and only uses make targets that exist."""

import json
import re

from django.conf import settings

REPO = settings.BASE_DIR.parent
RUNBOOK = (REPO / "RUNBOOK.md").read_text()
HEADINGS = set(re.findall(r"^#{2,3} (.+)$", RUNBOOK, re.M))


def test_the_sections_b6_promised_exist():
    for section in (
        "Deploy",
        "Rollback",
        "Restore from a backup",
        "Rotate a secret",
        "A job is overdue",
        "Sentry alert triage",
        "A free-tier limit is nearly hit",
        "Site or API is down",
        "One-time setup for monitoring, backups and CI",
    ):
        assert section in HEADINGS, section


def test_every_alert_points_to_a_section_that_exists():
    for path in sorted((REPO / "infra" / "monitoring").glob("alert-*.json")):
        content = json.loads(path.read_text().replace("${CHANNELS}", "[]"))["documentation"]["content"]
        named = re.findall(r'section "([^"]+)"', content)
        assert named, f"{path.name}: the alert text must name a RUNBOOK section"
        for section in named:
            assert section in HEADINGS, f"{path.name} points to '{section}', which RUNBOOK.md does not have"


def test_the_runbook_does_not_say_there_is_still_no_cap_or_no_ci():
    assert "not in the code yet" not in RUNBOOK
    assert "arrive in Stage 8" not in RUNBOOK


def test_retention_table_matches_the_settings():
    for name in (
        "EVENT_RETENTION_DAYS",
        "NOTIFICATION_READ_RETENTION_DAYS",
        "NOTIFICATION_RETENTION_DAYS",
        "WEBHOOK_EVENT_RETENTION_DAYS",
    ):
        assert name in RUNBOOK and hasattr(settings, name), name
