"""Realtime security (Stage 6): a member can only listen to their own notifications, to conversations they are in, and to circuits
they are part of. Tested against the local Postgres with two members' real, signed JWTs.

Supabase Realtime authorises a private channel by running `SELECT` on `realtime.messages` AS the signed-in user, with the
channel's topic in the `realtime.topic` setting and the verified JWT claims in `request.jwt.claims`. Row-level security on that
table decides. Plain Postgres has none of those pieces, so this test builds minimal stand-ins (role, auth.uid(), realtime.topic(),
the table), applies the SAME SQL our migrations apply (core/realtime_sql.py and messaging/0003), and asks the same question.
Everything is created inside the test's transaction and rolled back.
"""

import importlib
import json

import jwt
import pytest
from django.db import ProgrammingError, connection, transaction

from apps.circuits.models import Circuit, CircuitLeg, CircuitRound
from apps.matching.models import Capability
from apps.messaging.models import Conversation
from core import realtime_sql

pytestmark = pytest.mark.django_db

messaging_sql = importlib.import_module("apps.messaging.migrations.0003_realtime_access")

STAND_INS = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS realtime;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub', '')::uuid
$$;
CREATE OR REPLACE FUNCTION realtime.topic() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('realtime.topic', true), '')
$$;
CREATE TABLE realtime.messages (id bigserial PRIMARY KEY, topic text, extension text, payload jsonb);
ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;
GRANT USAGE ON SCHEMA auth, realtime TO authenticated;
GRANT EXECUTE ON FUNCTION auth.uid(), realtime.topic() TO authenticated;
GRANT SELECT ON realtime.messages TO authenticated;
INSERT INTO realtime.messages (topic, extension, payload) VALUES ('any', 'broadcast', '{}');
"""


@pytest.fixture(autouse=True)
def supabase_stand_ins():
    with connection.cursor() as cur:
        try:
            with transaction.atomic():
                cur.execute(STAND_INS)
        except ProgrammingError as exc:  # the dev database user may not be allowed to create roles
            pytest.skip(f"cannot create the stand-in roles on this database: {exc}")
        # the SQL under test, exactly as the migrations run it (the policies exist only where the realtime schema does)
        cur.execute(messaging_sql.FUNCTION + messaging_sql.POLICY)
        cur.execute(realtime_sql.FUNCTIONS + realtime_sql.POLICY)


@pytest.fixture
def claims_of(token_for, signing_key):
    """The verified claims of a member's real JWT, which is what Realtime hands to Postgres."""

    def _claims(member):
        return jwt.decode(token_for(member), signing_key.public_key(), algorithms=["ES256"], audience="authenticated")

    return _claims


def can_listen(claims: dict, topic: str) -> bool:
    """Would Realtime let this user join this topic? True if the authenticated role can read a row of realtime.messages."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT set_config('request.jwt.claims', %s, true), set_config('realtime.topic', %s, true)",
            [json.dumps(claims), topic],
        )
        cur.execute("SET LOCAL ROLE authenticated")
        try:
            cur.execute("SELECT count(*) FROM realtime.messages")
            return cur.fetchone()[0] > 0
        finally:
            cur.execute("RESET ROLE")


def make_circuit(make_member):
    cap = Capability.objects.order_by("id").first()  # the capability list is seeded by a migration
    people = [make_member("founder") for _ in range(3)]
    circuit = Circuit.objects.create(
        round=CircuitRound.objects.create(week="2026-W43"), score=0.8, consent_deadline="2030-01-01T00:00:00Z"
    )
    for i, giver in enumerate(people):
        CircuitLeg.objects.create(circuit=circuit, giver=giver, receiver=people[(i + 1) % 3], capability=cap)
    return circuit, people


# -- notifications: member:<id> -----------------------------------------------------------------------------
def test_a_member_hears_only_their_own_notification_channel(make_member, claims_of):
    a, b = make_member("student"), make_member("student")
    assert can_listen(claims_of(a), f"member:{a.pk}")
    assert can_listen(claims_of(b), f"member:{b.pk}")
    assert not can_listen(claims_of(a), f"member:{b.pk}")
    assert not can_listen(claims_of(b), f"member:{a.pk}")


def test_a_suspended_or_deleted_member_hears_nothing(make_member, claims_of):
    from django.utils import timezone

    for field in ("suspended_at", "deletion_requested_at", "deleted_at"):
        m = make_member("student", **{field: timezone.now()})
        assert not can_listen(claims_of(m), f"member:{m.pk}"), field


@pytest.mark.parametrize("suffix", ["", "abc", "1 OR 1=1", "1;DROP TABLE accounts_member", "-1", "9" * 19, "1:2", " 1", "1\n"])
def test_malformed_member_topics_are_refused(make_member, claims_of, suffix):
    a = make_member("student")
    assert not can_listen(claims_of(a), f"member:{suffix}")


def test_a_token_with_no_subject_hears_nothing(make_member, claims_of):
    a = make_member("student")
    claims = claims_of(a)
    del claims["sub"]
    assert not can_listen(claims, f"member:{a.pk}")
    assert not can_listen({}, f"member:{a.pk}")


def test_unknown_topics_are_refused_even_for_real_members(make_member, claims_of):
    a = make_member("student")
    for topic in ("notifications", "member", "admin:1", "realtime:broadcast", f"Member:{a.pk}", f"member:{a.pk}:extra"):
        assert not can_listen(claims_of(a), topic), topic


# -- chat: conversation:<id> --------------------------------------------------------------------------------
def test_only_the_two_people_in_a_conversation_hear_it(make_member, claims_of):
    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    conv = Conversation.objects.create(member_a_id=min(a.pk, b.pk), member_b_id=max(a.pk, b.pk), started_by=a, status="active")
    topic = f"conversation:{conv.pk}"
    assert can_listen(claims_of(a), topic) and can_listen(claims_of(b), topic)
    assert not can_listen(claims_of(c), topic)


def test_a_blocked_conversation_goes_silent_for_both(make_member, claims_of):
    a, b = make_member("student"), make_member("founder")
    conv = Conversation.objects.create(member_a_id=min(a.pk, b.pk), member_b_id=max(a.pk, b.pk), started_by=a, status="blocked")
    assert not can_listen(claims_of(a), f"conversation:{conv.pk}") and not can_listen(claims_of(b), f"conversation:{conv.pk}")


def test_blocking_through_the_api_silences_the_channel(make_member, connect, client_for, claims_of):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    cid = client_for(a).post("/api/conversations", {"member_id": b.pk, "body": "hi"}).json()["conversation"]["id"]
    assert can_listen(claims_of(b), f"conversation:{cid}")
    assert client_for(b).post(f"/api/members/{a.pk}/block").status_code == 204
    assert not can_listen(claims_of(a), f"conversation:{cid}") and not can_listen(claims_of(b), f"conversation:{cid}")


# -- circuits: circuit:<id> ---------------------------------------------------------------------------------
def test_only_the_three_members_of_a_circuit_hear_it(make_member, claims_of):
    circuit, people = make_circuit(make_member)
    outsider = make_member("founder")
    for p in people:
        assert can_listen(claims_of(p), f"circuit:{circuit.pk}")
    assert not can_listen(claims_of(outsider), f"circuit:{circuit.pk}")


def test_circuit_channels_are_not_guessable_across_circuits(make_member, claims_of):
    mine, my_people = make_circuit(make_member)
    other = Circuit.objects.create(round=mine.round, score=0.5, consent_deadline="2030-01-01T00:00:00Z")
    CircuitLeg.objects.create(
        circuit=other,
        giver=make_member("mentor"),
        receiver=make_member("mentor"),
        capability=Capability.objects.order_by("id").first(),
    )
    assert not can_listen(claims_of(my_people[0]), f"circuit:{other.pk}")
    assert can_listen(claims_of(my_people[0]), f"circuit:{mine.pk}")


def test_a_suspended_circuit_member_stops_hearing_it(make_member, claims_of):
    from django.utils import timezone

    circuit, people = make_circuit(make_member)
    people[0].suspended_at = timezone.now()
    people[0].save()
    assert not can_listen(claims_of(people[0]), f"circuit:{circuit.pk}") and can_listen(
        claims_of(people[1]), f"circuit:{circuit.pk}"
    )


# -- tables stay closed ------------------------------------------------------------------------------------
def test_the_authenticated_role_still_cannot_read_our_tables_directly(make_member, claims_of):
    a = make_member("student")
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('request.jwt.claims', %s, true)", [json.dumps(claims_of(a))])
        cur.execute("SET LOCAL ROLE authenticated")
        with pytest.raises(ProgrammingError), transaction.atomic():
            cur.execute("SELECT count(*) FROM accounts_member")
        cur.execute("RESET ROLE")


def test_the_check_functions_cannot_be_called_by_the_public_role(make_member):
    """Only `authenticated` may ask the yes/no question; anonymous Supabase clients (role `anon`) may not."""
    with connection.cursor() as cur:
        cur.execute("CREATE ROLE anon_probe NOLOGIN")
        cur.execute("SET LOCAL ROLE anon_probe")
        with pytest.raises(ProgrammingError), transaction.atomic():
            cur.execute("SELECT public.is_member_self(1, gen_random_uuid())")
        cur.execute("RESET ROLE")
