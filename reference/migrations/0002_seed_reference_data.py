from django.db import migrations


def forwards(apps, schema_editor):
    from reference.seed_data import seed_reference
    seed_reference(
        apps.get_model('reference', 'Region'),
        apps.get_model('reference', 'District'),
        apps.get_model('reference', 'Ward'),
        apps.get_model('reference', 'EntityType'),
        apps.get_model('reference', 'PaymentMethod'),
    )


class Migration(migrations.Migration):
    dependencies = [('reference', '0001_initial')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
