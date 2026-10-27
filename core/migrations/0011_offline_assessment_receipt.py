import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0010_offline_scan_receipt")]

    operations = [
        migrations.AddField(
            model_name="agronomiclog",
            name="offline_maturity_status",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.CreateModel(
            name="OfflineAssessmentReceipt",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("log", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                    related_name="offline_assessment_receipt", to="core.agronomiclog")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="offline_assessment_receipts", to="core.user")),
            ],
            options={"db_table": "offline_assessment_receipt"},
        ),
    ]
