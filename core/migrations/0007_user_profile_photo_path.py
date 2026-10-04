from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_admin_full_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_photo_path",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
