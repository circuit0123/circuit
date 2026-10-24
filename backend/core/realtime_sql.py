"""Who may listen to which private Realtime channel (Supabase Realtime "Broadcast" with private channels).

Our tables stay closed to Supabase clients (RLS on, privileges revoked). A client only gets to ask a yes/no question through
a SECURITY DEFINER function, and the policy on `realtime.messages` calls it with the topic of the channel the client joins:

    member:<id>   notifications for that member            -> only that member
    circuit:<id>  live status of an exchange circuit       -> only the three members of the circuit
    conversation:<id> chat (see messaging/0003)            -> only the two people in it

Broadcast payloads hold ids only; the app fetches the data from our API, which applies every privacy rule.
The policies exist only on Supabase (they need the `realtime` schema and the `authenticated` role). The same SQL is used by the
migration and by tests/unit/test_realtime_rls.py, which builds small stand-ins for those Supabase pieces.
"""

FUNCTIONS = """
CREATE OR REPLACE FUNCTION public.is_member_self(mid bigint, uid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM accounts_member m
    WHERE m.id = mid AND m.auth_user_id = uid
      AND m.suspended_at IS NULL AND m.deletion_requested_at IS NULL AND m.deleted_at IS NULL
  )
$$;
REVOKE ALL ON FUNCTION public.is_member_self(bigint, uuid) FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.is_circuit_member(cid bigint, uid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM circuits_circuitleg l
    JOIN accounts_member m ON m.id IN (l.giver_id, l.receiver_id)
    WHERE l.circuit_id = cid AND m.auth_user_id = uid
      AND m.suspended_at IS NULL AND m.deletion_requested_at IS NULL AND m.deleted_at IS NULL
  )
$$;
REVOKE ALL ON FUNCTION public.is_circuit_member(bigint, uuid) FROM PUBLIC;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT EXECUTE ON FUNCTION public.is_member_self(bigint, uuid) TO authenticated;
    GRANT EXECUTE ON FUNCTION public.is_circuit_member(bigint, uuid) TO authenticated;
  END IF;
END $$;
"""

POLICY = """
DO $$ BEGIN
  IF to_regclass('realtime.messages') IS NOT NULL AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    DROP POLICY IF EXISTS "members can listen to their own channels" ON realtime.messages;
    CREATE POLICY "members can listen to their own channels" ON realtime.messages FOR SELECT TO authenticated
    USING (
      CASE
        WHEN realtime.topic() ~ '^member:[0-9]{1,18}$'
          THEN public.is_member_self(split_part(realtime.topic(), ':', 2)::bigint, (SELECT auth.uid()))
        WHEN realtime.topic() ~ '^circuit:[0-9]{1,18}$'
          THEN public.is_circuit_member(split_part(realtime.topic(), ':', 2)::bigint, (SELECT auth.uid()))
        ELSE false
      END
    );
  END IF;
END $$;
"""

REVERSE = """
DO $$ BEGIN
  IF to_regclass('realtime.messages') IS NOT NULL THEN
    DROP POLICY IF EXISTS "members can listen to their own channels" ON realtime.messages;
  END IF;
END $$;
DROP FUNCTION IF EXISTS public.is_circuit_member(bigint, uuid);
DROP FUNCTION IF EXISTS public.is_member_self(bigint, uuid);
"""
