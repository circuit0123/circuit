"""Expand/contract (PRODUCTION.md §6): while a deploy rolls out, the previous release still writes to these tables.

Django drops a new column's default once it is added, so a NOT NULL column without a DATABASE default would make every
INSERT from the old code fail (first sign-in, compute_matches). Each new B4 column must have one, or be nullable.
"""

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db
B4_COLUMNS = [
    ("accounts_member", "onboarding"),
    ("accounts_member", "signup_source"),
    ("accounts_member", "is_simulated"),
    ("matching_matchresult", "features"),
    ("matching_matchresult", "position"),
    ("matching_matchresult", "arm"),
    ("matching_matchresult", "model_version"),
    ("matching_matchresult", "model_score"),
]


@pytest.mark.parametrize(("table", "column"), B4_COLUMNS)
def test_new_columns_can_be_left_out_of_an_insert(table, column):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT is_nullable, column_default FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            [table, column],
        )
        nullable, default = cur.fetchone()
    assert nullable == "YES" or default is not None, f"{table}.{column} would break the previous release's INSERTs"
