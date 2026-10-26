from django.db import migrations


def mint_to_emerald(apps, schema_editor):
    Member = apps.get_model("accounts", "Member")
    for member in Member.objects.filter(appearance__accent="mint").iterator():
        member.appearance = {**member.appearance, "accent": "emerald"}
        member.save(update_fields=["appearance"])


def emerald_to_mint(apps, schema_editor):
    Member = apps.get_model("accounts", "Member")
    for member in Member.objects.filter(appearance__accent="emerald").iterator():
        member.appearance = {**member.appearance, "accent": "mint"}
        member.save(update_fields=["appearance"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_onboarding_state_and_simulated")]
    operations = [migrations.RunPython(mint_to_emerald, emerald_to_mint)]
