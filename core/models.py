from django.db import models


class User(models.Model):
    fullname = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    password = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    province = models.CharField(max_length=120, blank=True, null=True)
    municipality = models.CharField(max_length=120, blank=True, null=True)
    barangay = models.CharField(max_length=120, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = "user"

    def __str__(self):
        return self.fullname


class Admin(models.Model):
    username = models.CharField(max_length=80, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=200)
    role = models.CharField(max_length=40, default="admin")
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = "admin"

    def __str__(self):
        return self.username


class Scan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scans")
    plot_name = models.CharField(max_length=80)
    grade = models.CharField(max_length=2)
    maturity_pct = models.IntegerField()
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scan"


class AuditLog(models.Model):
    user_id = models.IntegerField(blank=True, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"


class SystemConfig(models.Model):
    system_name = models.CharField(max_length=120, default="CaneDustry")
    maintenance_mode = models.BooleanField(default=False)
    model_filename = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_config"


class Notification(models.Model):
    title = models.CharField(max_length=120)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "notification"


class Feedback(models.Model):
    user_id = models.IntegerField(blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedback"


class AgronomicLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agronomic_logs")
    variety = models.CharField(max_length=120, blank=True, null=True)
    hectares = models.CharField(max_length=50, blank=True, null=True)
    plowing_count = models.CharField(max_length=20, blank=True, null=True)
    weeding_count = models.CharField(max_length=20, blank=True, null=True)
    fertilizer_count = models.CharField(max_length=20, blank=True, null=True)
    ratoon_stage = models.CharField(max_length=40, blank=True, null=True)
    rssi_infected = models.CharField(max_length=20, blank=True, null=True)
    predicted_lkg_tc = models.FloatField(blank=True, null=True)
    predicted_tc_ha = models.FloatField(blank=True, null=True)
    predicted_lkg = models.FloatField(blank=True, null=True)
    recommendations_summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agronomic_log"


class CvScanUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cv_scan_uploads")
    image_path = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    variety = models.CharField(max_length=120, blank=True, null=True)
    maturity_status = models.CharField(max_length=40, blank=True, null=True)
    model_name = models.CharField(max_length=120, blank=True, null=True)
    confidence = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cv_scan_upload"
