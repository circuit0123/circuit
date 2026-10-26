"""Dev-only commands refuse a remote database, so ENV=dev plus a real DATABASE_URL can never wipe a real environment."""

import pytest
from django.core.management import CommandError, call_command

from core import devguard

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "command, args",
    [("reset_demo", []), ("delete_member", ["--member", "1"]), ("export_member", ["--member", "1"]), ("simulate_network", [])],
)
def test_dev_only_commands_refuse_a_remote_database(monkeypatch, command, args):
    monkeypatch.setattr(devguard, "_database_host", lambda: "aws-0-ap-south-1.pooler.supabase.com")
    with pytest.raises(CommandError, match="only runs against a database on this computer"):
        call_command(command, *args)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "db"])
def test_local_hosts_pass(monkeypatch, host):
    monkeypatch.setattr(devguard, "_database_host", lambda: host)
    devguard.require_local_database("anything")  # no exception


def test_it_only_applies_on_a_dev_environment(monkeypatch, settings):
    monkeypatch.setattr(devguard, "_database_host", lambda: "db.example.com")
    settings.ENV = "demo"  # demo legitimately uses a remote database; its own ENV checks apply
    devguard.require_local_database("reset_demo")
