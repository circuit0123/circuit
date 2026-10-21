"""Row-level security, deny by default (CLAUDE.md / PRODUCTION.md §3).

RLS is enabled on every table in `public` with NO policies, so Supabase's
`anon` and `authenticated` roles (PostgREST / Realtime) can read nothing.
The Django app connects as the table owner, which bypasses RLS, so it is the
only writer. Never FORCE RLS and never use the Supabase service-role key in
the frontend. Runs after every migrate so new tables are covered too.
"""

import structlog
from django.conf import settings
from django.db import connection

log = structlog.get_logger("rls")

# PostGIS-owned reference table; not ours to alter.
_SKIP = {"spatial_ref_sys"}

_FIND = """
SELECT c.relname FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  AND NOT c.relrowsecurity AND c.relowner = (SELECT usesysid FROM pg_user WHERE usename = current_user)
"""


_STILL_OPEN = """
SELECT c.relname FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
"""

CLIENT_ROLES = ("anon", "authenticated")  # Supabase's roles for PostgREST / Realtime (they do not exist on a bare Postgres)


def enable_rls(**kwargs) -> None:
    with connection.cursor() as cur:
        cur.execute(_FIND)
        for (table,) in cur.fetchall():
            if table not in _SKIP:
                cur.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        # Tables owned by another role are skipped above. A table left open is readable through Supabase's public
        # API with the anon key that ships in the frontend, so outside dev this stops the migration.
        cur.execute(_STILL_OPEN)
        open_tables = sorted(t for (t,) in cur.fetchall() if t not in _SKIP)
    if open_tables:
        if settings.ENV == "dev":
            log.error("rls_missing", tables=open_tables)
        else:
            raise RuntimeError(f"Row-level security is off for: {', '.join(open_tables)}. Fix table ownership before deploying.")


def revoke_client_privileges(**kwargs) -> None:
    """Second lock behind RLS: Supabase's client roles get no table privileges unless a later stage grants them one by one.

    Run once from a migration, not after every migrate, so a deliberate GRANT (Stage 6, Realtime) is not undone.
    """
    with connection.cursor() as cur:
        for role in CLIENT_ROLES:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if not cur.fetchone():
                continue
            for kind in ("TABLES", "SEQUENCES"):
                cur.execute(f'REVOKE ALL ON ALL {kind} IN SCHEMA public FROM "{role}"')
                cur.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON {kind} FROM "{role}"')
