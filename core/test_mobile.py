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

    @override_settings(FARMER_ONLY=True)
    def test_mobile_language_news_about_and_favicon(self):
        session = self.client.session
        session["user_id"] = self.farmer.pk
        session.save()
        for path in ("/farmer/news", "/about-viscane", "/favicon.ico"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        about = self.client.get("/about-viscane")
        self.assertContains(about, 'href="/homepage"')
        self.assertNotContains(about, 'href="/auth?mode=login"')
        news = self.client.get("/farmer/news")
        self.assertContains(news, '/static/images/access-cane.svg')
        language = self.client.post("/i18n/setlang/", {"language": "en", "next": "/farmer/settings"})
        self.assertEqual(language.status_code, 302)
        self.assertEqual(language["Location"], "/farmer/settings")
        self.assertEqual(self.client.get("/admin-login").status_code, 403)

    @override_settings(FARMER_ONLY=False)
    def test_apk_marker_can_switch_language(self):
        client = Client(HTTP_USER_AGENT="Android ViscaneFarmer/1.0")
        response = client.post("/i18n/setlang/", {"language": "en", "next": "/farmer/settings"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/farmer/settings")
        self.assertEqual(client.get("/favicon.ico").status_code, 200)
        self.assertEqual(client.get("/admin-login").status_code, 403)

    @override_settings(FARMER_ONLY=False)
    def test_apk_menu_pages_and_notifications_use_dashboard_path(self):
        client = Client(HTTP_USER_AGENT="Android ViscaneFarmer/1.0")
        session = client.session
        session["user_id"] = self.farmer.pk
        session.save()
        dashboard = client.get("/homepage")
        self.assertContains(dashboard, 'href="/homepage?view=news"')
        self.assertContains(dashboard, 'href="/homepage?view=about"')
        self.assertContains(client.get("/homepage?view=news"), 'id="farmer-feedback-message"')
        self.assertContains(client.get("/homepage?view=about"), 'href="/homepage"')
        self.assertEqual(client.get("/homepage?view=notifications").status_code, 200)
        self.assertEqual(client.post("/homepage?view=notifications", {
            "announcement_id": 0, "suggestion_id": 0,
        }).status_code, 200)
        feedback = client.post("/farmer/feedback", {
            "feedback_message": "Mobile feedback", "return_to": "news",
        })
        self.assertTrue(feedback["Location"].startswith("/homepage?view=news&"))

    @override_settings(FARMER_ONLY=False)
    def test_apk_profile_photo_uses_dashboard_path(self):
        client = Client(HTTP_USER_AGENT="Android ViscaneFarmer/1.0")
        session = client.session
        session["user_id"] = self.farmer.pk
        session.save()
        with tempfile.TemporaryDirectory() as folder, override_settings(PRIVATE_UPLOAD_ROOT=Path(folder)):
            photo_dir = Path(folder) / "profile_photos"
            photo_dir.mkdir()
            photo = BytesIO()
            Image.new("RGB", (2, 2), "green").save(photo, format="JPEG")
            (photo_dir / "mobile.jpg").write_bytes(photo.getvalue())
            self.farmer.profile_photo_path = "mobile.jpg"
            self.farmer.save(update_fields=["profile_photo_path"])
            self.assertContains(client.get("/farmer/settings"), 'src="/homepage?view=profile-photo"')
            response = client.get("/homepage?view=profile-photo")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), photo.getvalue())
            response.close()

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
