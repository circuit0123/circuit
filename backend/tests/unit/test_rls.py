import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def test_non_owner_roles_read_nothing(make_member):
    """What Supabase's anon/authenticated roles are: a role with SELECT but no policy sees zero rows."""
    make_member()
    with connection.cursor() as cur:
        cur.execute("CREATE ROLE circuit_rls_probe NOLOGIN")
        cur.execute("GRANT SELECT ON accounts_member TO circuit_rls_probe")
        cur.execute("SELECT count(*) FROM accounts_member")
        assert cur.fetchone()[0] == 1  # the app role (table owner) sees it
        cur.execute("SET LOCAL ROLE circuit_rls_probe")
        cur.execute("SELECT count(*) FROM accounts_member")
        assert cur.fetchone()[0] == 0
        cur.execute("RESET ROLE")
