from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0011_offline_assessment_receipt")]

    operations = [
        migrations.AddField(
            model_name="feedback",
            name="offline_id",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]
