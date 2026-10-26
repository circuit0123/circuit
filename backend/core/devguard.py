"""Safety net for commands that wipe or delete things and are meant for a laptop.

Those commands check `ENV == "dev"`. But ENV is just a setting: someone who points DATABASE_URL at the real database while ENV
stays "dev" (for example to create the first admin user with `make admin-user`, RUNBOOK.md) would otherwise be able to run
`make reset-demo` against production. So on ENV=dev they also require the database to be on this machine.
"""

from django.conf import settings
from django.core.management.base import CommandError

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "host.docker.internal"}  # "db" = the docker compose service


def _database_host() -> str:
    return settings.DATABASES["default"].get("HOST") or ""


def require_local_database(command: str) -> None:
    if settings.ENV == "dev" and _database_host() not in LOCAL_HOSTS:
        raise CommandError(
            f"{command} only runs against a database on this computer, and DATABASE_URL points at {_database_host() or 'a remote host'}. "
            "Refusing, in case that is a real environment."
        )
