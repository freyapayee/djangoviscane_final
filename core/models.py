from django.db import models


class User(models.Model):
    seen_announcement_id = models.PositiveIntegerField(default=0)
    seen_suggestion_id = models.PositiveIntegerField(default=0)
    fullname = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    password = models.CharField(max_length=200)
    profile_photo_path = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    province = models.CharField(max_length=120, blank=True, null=True)
    municipality = models.CharField(max_length=120, blank=True, null=True)
    barangay = models.CharField(max_length=120, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    restriction_type = models.CharField(max_length=20, blank=True, default="")
    restriction_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "user"

    def __str__(self):
        return self.fullname


class Admin(models.Model):
    username = models.CharField(max_length=80, unique=True)
    full_name = models.CharField(max_length=100, blank=True, default="")
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
    cv_upload = models.ForeignKey("CvScanUpload", on_delete=models.SET_NULL, related_name="scans", null=True, blank=True)
    hidden_from_recent = models.BooleanField(default=False)
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


class FeedbackReply(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name="replies")
    admin = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedback_reply"


class AgronomicLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agronomic_logs")
    scan = models.ForeignKey(Scan, on_delete=models.SET_NULL, related_name="agronomic_logs", null=True, blank=True)
    offline_cv_upload = models.ForeignKey("CvScanUpload", on_delete=models.SET_NULL, related_name="offline_agronomic_logs", null=True, blank=True)
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
    recommendations_snapshot = models.JSONField(default=list, blank=True)
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


class OfflineScanReceipt(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="offline_scan_receipts")
    log = models.OneToOneField(AgronomicLog, on_delete=models.CASCADE, related_name="offline_receipt")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "offline_scan_receipt"
