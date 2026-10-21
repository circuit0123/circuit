from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION events_event_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'events_event is append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER events_event_no_update_delete
BEFORE UPDATE OR DELETE ON events_event
FOR EACH ROW EXECUTE FUNCTION events_event_append_only();
"""
REVERSE = "DROP TRIGGER events_event_no_update_delete ON events_event; DROP FUNCTION events_event_append_only();"


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
