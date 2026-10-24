from django.db import migrations

from core.realtime_sql import FUNCTIONS, POLICY, REVERSE


class Migration(migrations.Migration):
    # Realtime channels for notifications (member:<id>) and circuit status (circuit:<id>). Functions work on any Postgres;
    # the policy is created only where Supabase's realtime schema exists. See core/realtime_sql.py.
    dependencies = [
        ("core", "0006_b3_account_basics"),
        ("accounts", "0007_b3_account_basics"),
        ("circuits", "0001_initial"),
    ]
    operations = [migrations.RunSQL(FUNCTIONS + POLICY, REVERSE)]
