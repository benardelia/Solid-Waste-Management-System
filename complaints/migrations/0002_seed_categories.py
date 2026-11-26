from django.db import migrations


def forwards(apps, schema_editor):
    from complaints.seed_data import seed_complaint_categories
    seed_complaint_categories(apps.get_model('complaints', 'ComplaintCategory'))


class Migration(migrations.Migration):
    dependencies = [('complaints', '0001_initial')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
