from django.db import migrations

# Who may listen to a conversation's private Realtime channel ("conversation:<id>").
# The function is SECURITY DEFINER (runs as the table owner), so Supabase clients never get read access to our tables:
# they can only ask "am I in this conversation?". The policy on realtime.messages exists only on Supabase.
FUNCTION = """
CREATE OR REPLACE FUNCTION public.is_conversation_member(conv_id bigint, uid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM messaging_conversation c
    JOIN accounts_member m ON m.id IN (c.member_a_id, c.member_b_id)
    WHERE c.id = conv_id AND m.auth_user_id = uid AND c.status <> 'blocked' AND m.suspended_at IS NULL
  )
$$;
REVOKE ALL ON FUNCTION public.is_conversation_member(bigint, uuid) FROM PUBLIC;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT EXECUTE ON FUNCTION public.is_conversation_member(bigint, uuid) TO authenticated;
  END IF;
END $$;
"""

POLICY = """
DO $$ BEGIN
  IF to_regclass('realtime.messages') IS NOT NULL AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    DROP POLICY IF EXISTS "conversation members can listen" ON realtime.messages;
    CREATE POLICY "conversation members can listen" ON realtime.messages FOR SELECT TO authenticated
    USING (
      CASE WHEN realtime.topic() ~ '^conversation:[0-9]{1,18}$'
        THEN public.is_conversation_member(split_part(realtime.topic(), ':', 2)::bigint, (SELECT auth.uid()))
        ELSE false END
    );
  END IF;
END $$;
"""

REVERSE = """
DO $$ BEGIN
  IF to_regclass('realtime.messages') IS NOT NULL THEN
    DROP POLICY IF EXISTS "conversation members can listen" ON realtime.messages;
  END IF;
END $$;
DROP FUNCTION IF EXISTS public.is_conversation_member(bigint, uuid);
"""


class Migration(migrations.Migration):
    dependencies = [("messaging", "0002_initial")]
    operations = [migrations.RunSQL(FUNCTION + POLICY, REVERSE)]
