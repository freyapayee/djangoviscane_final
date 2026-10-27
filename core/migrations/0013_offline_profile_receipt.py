import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0012_feedback_offline_id")]

    operations = [
        migrations.CreateModel(
            name="OfflineProfileReceipt",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="offline_profile_receipts", to="core.user")),
            ],
            options={"db_table": "offline_profile_receipt"},
        ),
    ]
