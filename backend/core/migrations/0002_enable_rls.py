from django.db import migrations

from core.rls import enable_rls


def forwards(apps, schema_editor):
    enable_rls()


class Migration(migrations.Migration):
    """Deny-by-default RLS on every table that exists so far. core.rls also re-runs after every migrate for new tables."""

    dependencies = [("core", "0001_ratelimit_hit")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
