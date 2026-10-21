from django.db import migrations

from core.rls import revoke_client_privileges


def forwards(apps, schema_editor):
    revoke_client_privileges()


class Migration(migrations.Migration):
    """Defence in depth behind RLS: Supabase's anon/authenticated roles hold no table privileges (no-op without them)."""

    dependencies = [("core", "0002_enable_rls")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
