from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fullname", models.CharField(max_length=100)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("phone", models.CharField(max_length=20)),
                ("password", models.CharField(max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("province", models.CharField(blank=True, max_length=120, null=True)),
                ("municipality", models.CharField(blank=True, max_length=120, null=True)),
                ("barangay", models.CharField(blank=True, max_length=120, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_archived", models.BooleanField(default=False)),
            ],
            options={"db_table": "user"},
        ),
        migrations.CreateModel(
            name="Admin",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=80, unique=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password_hash", models.CharField(max_length=200)),
                ("role", models.CharField(default="admin", max_length=40)),
                ("is_archived", models.BooleanField(default=False)),
            ],
            options={"db_table": "admin"},
        ),
        migrations.CreateModel(
            name="SystemConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("system_name", models.CharField(default="CaneDustry", max_length=120)),
                ("maintenance_mode", models.BooleanField(default=False)),
                ("model_filename", models.CharField(blank=True, max_length=255, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "system_config"},
        ),
        migrations.CreateModel(
            name="Scan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plot_name", models.CharField(max_length=80)),
                ("grade", models.CharField(max_length=2)),
                ("maturity_pct", models.IntegerField()),
                ("status", models.CharField(default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scans", to="core.user")),
            ],
            options={"db_table": "scan"},
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.IntegerField(blank=True, null=True)),
            ],
            options={"db_table": "notification"},
        ),
        migrations.CreateModel(
            name="Feedback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.IntegerField(blank=True, null=True)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "feedback"},
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.IntegerField(blank=True, null=True)),
                ("action", models.CharField(max_length=255)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "audit_log"},
        ),
        migrations.CreateModel(
            name="AgronomicLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variety", models.CharField(blank=True, max_length=120, null=True)),
                ("hectares", models.CharField(blank=True, max_length=50, null=True)),
                ("plowing_count", models.CharField(blank=True, max_length=20, null=True)),
                ("weeding_count", models.CharField(blank=True, max_length=20, null=True)),
                ("fertilizer_count", models.CharField(blank=True, max_length=20, null=True)),
                ("ratoon_stage", models.CharField(blank=True, max_length=40, null=True)),
                ("rssi_infected", models.CharField(blank=True, max_length=20, null=True)),
                ("predicted_lkg_tc", models.FloatField(blank=True, null=True)),
                ("predicted_tc_ha", models.FloatField(blank=True, null=True)),
                ("predicted_lkg", models.FloatField(blank=True, null=True)),
                ("recommendations_summary", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agronomic_logs", to="core.user")),
            ],
            options={"db_table": "agronomic_log"},
        ),
        migrations.CreateModel(
            name="CvScanUpload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image_path", models.CharField(max_length=255)),
                ("original_filename", models.CharField(blank=True, max_length=255, null=True)),
                ("variety", models.CharField(blank=True, max_length=120, null=True)),
                ("maturity_status", models.CharField(blank=True, max_length=40, null=True)),
                ("model_name", models.CharField(blank=True, max_length=120, null=True)),
                ("confidence", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cv_scan_uploads", to="core.user")),
            ],
            options={"db_table": "cv_scan_upload"},
        ),
    ]
