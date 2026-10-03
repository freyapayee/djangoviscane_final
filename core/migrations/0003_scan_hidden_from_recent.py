from django.db import migrations, models


def hide_previously_removed_pictures(apps, schema_editor):
    Scan = apps.get_model("core", "Scan")
    Scan.objects.filter(cv_upload_id__isnull=True).update(hidden_from_recent=True)


class Migration(migrations.Migration):
    dependencies = [("core", "0002_scan_cv_upload")]

    operations = [
        migrations.AddField(
            model_name="scan",
            name="hidden_from_recent",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(hide_previously_removed_pictures, migrations.RunPython.noop),
    ]
