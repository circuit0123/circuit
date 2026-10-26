from django.db import migrations

# Events stay append-only: UPDATE is still always refused, and DELETE is refused too, except inside a transaction that has switched on
# `circuit.purge_events` (apps/accounts/retention.py does that, once a day, for rows older than EVENT_RETENTION_DAYS). A stray
# `Event.objects.filter(...).delete()` anywhere else still fails.
SQL = """
CREATE OR REPLACE FUNCTION events_event_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_setting('circuit.purge_events', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'events_event is append-only';
END;
$$ LANGUAGE plpgsql;
"""
REVERSE = """
CREATE OR REPLACE FUNCTION events_event_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'events_event is append-only';
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0002_append_only")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
