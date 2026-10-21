"""Row-level security, deny by default (CLAUDE.md / PRODUCTION.md §3).

RLS is enabled on every table in `public` with NO policies, so Supabase's
`anon` and `authenticated` roles (PostgREST / Realtime) can read nothing.
The Django app connects as the table owner, which bypasses RLS, so it is the
only writer. Never FORCE RLS and never use the Supabase service-role key in
the frontend. Runs after every migrate so new tables are covered too.
"""

from django.db import connection

# PostGIS-owned reference table; not ours to alter.
_SKIP = {"spatial_ref_sys"}

_FIND = """
SELECT c.relname FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  AND NOT c.relrowsecurity AND c.relowner = (SELECT usesysid FROM pg_user WHERE usename = current_user)
"""


def enable_rls(**kwargs) -> None:
    with connection.cursor() as cur:
        cur.execute(_FIND)
        for (table,) in cur.fetchall():
            if table not in _SKIP:
                cur.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
