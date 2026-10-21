from django.db import migrations

from apps.matching.lists import sync_lists


def load(apps, schema_editor):
    sync_lists(apps.get_model("matching", "Capability"), apps.get_model("matching", "Trait"))


class Migration(migrations.Migration):
    dependencies = [("matching", "0001_initial")]
    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
