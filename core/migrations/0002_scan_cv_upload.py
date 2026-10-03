from datetime import timedelta

from django.db import migrations, models
import django.db.models.deletion


def link_existing_scans(apps, schema_editor):
    Scan = apps.get_model("core", "Scan")
    CvScanUpload = apps.get_model("core", "CvScanUpload")
    used_upload_ids = set()
    for scan in Scan.objects.order_by("created_at", "pk").iterator():
        upload = (
            CvScanUpload.objects.filter(
                user_id=scan.user_id,
                created_at__lte=scan.created_at,
                created_at__gte=scan.created_at - timedelta(minutes=10),
            )
            .exclude(pk__in=used_upload_ids)
            .order_by("-created_at", "-pk")
            .first()
        )
        if upload:
            Scan.objects.filter(pk=scan.pk).update(cv_upload_id=upload.pk)
            used_upload_ids.add(upload.pk)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="scan",
            name="cv_upload",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="scans",
                to="core.cvscanupload",
            ),
        ),
        migrations.RunPython(link_existing_scans, migrations.RunPython.noop),
    ]
