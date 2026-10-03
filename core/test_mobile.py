from io import BytesIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import User, CvScanUpload


class FarmerMobileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.farmer = User.objects.create(fullname="Mobile Farmer", email="mobile@example.invalid",
            phone="09123456789", password=make_password("Mobile-test-123!"))

    @override_settings(FARMER_ONLY=True)
    def test_farmer_deployment_blocks_admin_without_client_marker(self):
        self.assertNotContains(self.client.get("/"), "Admin Portal")
        for route in ["/admin", "/admin-access", "/admin-login", "/superadmin-login",
                      "/admin-setup", "/superadmin", "/superadmin/settings", "/unknown"]:
            self.assertEqual(self.client.get(route).status_code, 403, route)
            self.assertEqual(self.client.post(route).status_code, 403, route)
        self.assertEqual(self.client.get("/auth").status_code, 200)

    def test_apk_marker_hides_admin_and_blocks_navigation(self):
        client = Client(HTTP_USER_AGENT="Android ViscaneFarmer/1.0")
        self.assertNotContains(client.get("/"), "Admin Portal")
        self.assertEqual(client.get("/admin-login").status_code, 403)
        self.assertContains(self.client.get("/"), "Admin Portal")

    def test_csrf_required_and_login_rotates_session(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/auth")
        credentials = {"email": self.farmer.email, "password": "Mobile-test-123!"}
        self.assertEqual(client.post("/auth", credentials).status_code, 403)
        session = client.session
        session["admin_id"] = 999
        session.save()
        old_key = session.session_key
        client.cookies["sessionid"] = old_key
        response = client.post("/auth", {**credentials, "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(client.session.session_key, old_key)
        self.assertNotIn("admin_id", client.session)
        for route in ["/farmer/settings", "/farmer/feedback", "/calculate", "/api/scan/predict", "/scan/new"]:
            self.assertEqual(client.post(route, {}).status_code, 403, route)
        client.get("/logout")
        self.assertNotIn("user_id", client.session)

    def test_invalid_uploads_never_reach_predictor(self):
        self.client.post("/auth", {"email": self.farmer.email, "password": "Mobile-test-123!"})
        with patch("core.views.request_prediction_service") as predictor:
            response = self.client.post("/api/scan/predict", {"file": SimpleUploadedFile("fake.jpg", b"not an image")})
            self.assertEqual(response.status_code, 400)
            with override_settings(SCAN_MAX_IMAGE_BYTES=1):
                response = self.client.post("/api/scan/predict", {"file": SimpleUploadedFile("big.jpg", b"xx")})
                self.assertEqual(response.status_code, 413)
            predictor.assert_not_called()

    @override_settings(FARMER_ONLY=True)
    def test_scan_images_require_ownership(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(PRIVATE_UPLOAD_ROOT=Path(folder)):
            path = Path(folder) / "private/cv_scans/test.jpg"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"test-image")
            upload = CvScanUpload.objects.create(user=self.farmer, image_path="private/cv_scans/test.jpg")
            url = f"/farmer/cv-upload/{upload.pk}/image"
            self.assertEqual(self.client.get(url).status_code, 404)
            other = User.objects.create(fullname="Other", email="other-mobile@example.invalid", phone="0", password="unused")
            session = self.client.session
            session["user_id"] = other.pk
            session.save()
            self.assertEqual(self.client.get(url).status_code, 404)
            session["user_id"] = self.farmer.pk
            session.save()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"test-image")
            response.close()
            self.assertEqual(self.client.get("/static/uploads/cv_scans/test.jpg").status_code, 403)
