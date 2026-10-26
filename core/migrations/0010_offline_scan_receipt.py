import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0009_user_restriction_reason_user_restriction_type_and_more")]

    operations = [
        migrations.AddField(
            model_name="agronomiclog",
            name="offline_cv_upload",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="offline_agronomic_logs",
                to="core.cvscanupload",
            ),
        ),
        migrations.CreateModel(
            name="OfflineScanReceipt",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("log", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="offline_receipt", to="core.agronomiclog")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="offline_scan_receipts", to="core.user")),
            ],
            options={"db_table": "offline_scan_receipt"},
        ),
    ]
