from io import BytesIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import User, CvScanUpload, AgronomicLog, Feedback, Notification, OfflineAssessmentReceipt, OfflineProfileReceipt, OfflineScanReceipt


class FarmerMobileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.farmer = User.objects.create(fullname="Mobile Farmer", email="mobile@example.invalid",
            phone="09123456789", password=make_password("Mobile-test-123!"))

    def test_offline_scan_sync_is_farmer_owned_and_idempotent(self):
        import uuid
        record_id = str(uuid.uuid4())
        photo = BytesIO()
        Image.new("RGB", (8, 8), "green").save(photo, format="JPEG")
        payload = {
            "record_id": record_id,
            "farmer_id": str(self.farmer.pk),
            "label": "524__Mature",
            "confidence": "0.94",
            "resnet18_sha256": "37be5dd4ccf618a94d86d0e3a26e040e0617c6827cdb00ec74548aa426f66823",
            "yolov8_sha256": "cdf5b713b21bf9fa83924857b10ff3c923d91c1e5457a3f68221700b99b7ca48",
        }
        with tempfile.TemporaryDirectory() as folder, override_settings(PRIVATE_UPLOAD_ROOT=Path(folder), VISCANE_OFFLINE=False):
            self.assertEqual(self.client.get("/api/mobile/session").status_code, 401)
            self.assertEqual(self.client.post("/api/mobile/offline-scan", payload).status_code, 401)
            session = self.client.session
            session["user_id"] = self.farmer.pk
            session.save()
            self.assertEqual(self.client.get("/api/mobile/session").json()["farmer_id"], self.farmer.pk)
            self.assertEqual(self.client.post("/api/mobile/offline-scan", {**payload, "label": "unknown"}).status_code, 400)
            self.assertEqual(self.client.post("/api/mobile/offline-scan", {**payload, "resnet18_sha256": "wrong"}).status_code, 400)
            strict = Client(enforce_csrf_checks=True)
            strict_session = strict.session
            strict_session["user_id"] = self.farmer.pk
            strict_session.save()
            self.assertEqual(strict.post("/api/mobile/offline-scan", payload).status_code, 403)
            first = self.client.post("/api/mobile/offline-scan", {
                **payload,
                "file": SimpleUploadedFile("cane.jpg", photo.getvalue(), content_type="image/jpeg"),
            })
            self.assertEqual(first.status_code, 201, first.content)
            self.assertEqual(first.json()["record_id"], record_id)
            self.assertEqual(self.client.post("/api/mobile/offline-scan", payload).status_code, 200)
            self.assertEqual(OfflineScanReceipt.objects.count(), 1)
            self.assertEqual(AgronomicLog.objects.filter(user=self.farmer, offline_cv_upload__isnull=False).count(), 1)
            self.assertEqual(CvScanUpload.objects.filter(user=self.farmer).count(), 1)
            other = User.objects.create(fullname="Other Farmer", email="other@example.invalid", phone="09123456788", password="unused")
            session = self.client.session
            session["user_id"] = other.pk
            session.save()
            self.assertEqual(self.client.post("/api/mobile/offline-scan", payload).status_code, 403)

    def test_offline_assessment_sync_recomputes_and_is_farmer_owned(self):
        import uuid
        record_id = str(uuid.uuid4())
        payload = {
            "record_id": record_id, "farmer_id": str(self.farmer.pk),
            "variety": "0", "hectares": "1.5", "plowing": "1", "weeding": "1",
            "fertilizer": "1", "stage": "1", "infected": "false", "maturity": "2",
        }
        self.assertEqual(self.client.post("/api/mobile/offline-assessment", payload).status_code, 401)
        session = self.client.session
        session["user_id"] = self.farmer.pk
        session.save()
        strict = Client(enforce_csrf_checks=True)
        strict_session = strict.session
        strict_session["user_id"] = self.farmer.pk
        strict_session.save()
        self.assertEqual(strict.post("/api/mobile/offline-assessment", payload).status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-assessment", {**payload, "farmer_id": "999"}).status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-assessment", {**payload, "plowing": "4"}).status_code, 400)
        self.assertEqual(self.client.post("/api/mobile/offline-assessment", {**payload, "scan_id": str(uuid.uuid4())}).status_code, 409)
        first = self.client.post("/api/mobile/offline-assessment", payload)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["record_id"], record_id)
        self.assertEqual(self.client.post("/api/mobile/offline-assessment", payload).status_code, 200)
        self.assertEqual(OfflineAssessmentReceipt.objects.count(), 1)
        log = OfflineAssessmentReceipt.objects.get(pk=record_id).log
        self.assertEqual(log.user_id, self.farmer.pk)
        self.assertAlmostEqual(log.predicted_lkg_tc, 1.836)
        self.assertAlmostEqual(log.predicted_tc_ha, 322.65)
        self.assertTrue(log.recommendations_snapshot)
        self.assertEqual(AgronomicLog.objects.filter(user=self.farmer).count(), 1)
        other = User.objects.create(fullname="Other Farmer", email="second@example.invalid", phone="09123456788", password="unused")
        session = self.client.session
        session["user_id"] = other.pk
        session.save()
        self.assertEqual(self.client.post("/api/mobile/offline-assessment", payload).status_code, 403)

    def test_offline_content_feedback_and_profile_are_farmer_owned(self):
        import uuid
        Notification.objects.create(title="Harvest bulletin", message="Saved when connected")
        AgronomicLog.objects.create(user=self.farmer, variety="VMC 84-524", predicted_lkg=123.0)
        self.assertEqual(self.client.get("/api/mobile/offline-content").status_code, 401)
        session = self.client.session
        session["user_id"] = self.farmer.pk
        session.save()
        snapshot = self.client.get("/api/mobile/offline-content")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["farmer_id"], self.farmer.pk)
        self.assertEqual(snapshot.json()["announcements"][0]["title"], "Harvest bulletin")
        self.assertEqual(snapshot.json()["history"][0]["predicted_lkg"], 123.0)
        feedback_id = str(uuid.uuid4())
        feedback = {"record_id": feedback_id, "farmer_id": str(self.farmer.pk), "message": "Field feedback"}
        strict = Client(enforce_csrf_checks=True)
        strict_session = strict.session
        strict_session["user_id"] = self.farmer.pk
        strict_session.save()
        self.assertEqual(strict.post("/api/mobile/offline-feedback", feedback).status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-feedback", feedback).status_code, 201)
        self.assertEqual(self.client.post("/api/mobile/offline-feedback", feedback).status_code, 200)
        self.assertEqual(Feedback.objects.filter(offline_id=feedback_id, user_id=self.farmer.pk).count(), 1)
        self.assertEqual(self.client.get("/api/mobile/offline-content").json()["feedback"][0]["offline_id"], feedback_id)
        profile_id = str(uuid.uuid4())
        profile = {"record_id": profile_id, "farmer_id": str(self.farmer.pk),
                   "original_email": self.farmer.email,
                   "original_version": snapshot.json()["profile"]["version"],
                   "email": "updated@example.invalid",
                   "phone": "09123456780", "province": "Negros Occidental",
                   "municipality": "Isabela", "barangay": "Barangay 1"}
        self.assertEqual(strict.post("/api/mobile/offline-profile", profile).status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-profile", profile).status_code, 201)
        self.assertEqual(self.client.post("/api/mobile/offline-profile", profile).status_code, 200)
        self.assertEqual(OfflineProfileReceipt.objects.filter(pk=profile_id).count(), 1)
        self.farmer.refresh_from_db()
        self.assertEqual(self.farmer.email, "updated@example.invalid")
        self.assertEqual(self.client.post("/api/mobile/offline-profile",
            {**profile, "record_id": str(uuid.uuid4())}).status_code, 409)
        other = User.objects.create(fullname="Other Farmer", email="other-farmer@example.invalid",
            phone="09123456781", password="unused")
        session = self.client.session
        session["user_id"] = other.pk
        session.save()
        self.assertEqual(self.client.post("/api/mobile/offline-feedback", feedback).status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-profile", profile).status_code, 403)

    @override_settings(VISCANE_OFFLINE=True)
    def test_embedded_django_cannot_acknowledge_production_sync(self):
        session = self.client.session
        session["user_id"] = self.farmer.pk
        session.save()
        self.assertEqual(self.client.get("/api/mobile/session").status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-scan", {}).status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-assessment", {}).status_code, 403)
        self.assertEqual(self.client.get("/api/mobile/offline-content").status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-feedback", {}).status_code, 403)
        self.assertEqual(self.client.post("/api/mobile/offline-profile", {}).status_code, 403)

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
        cover = client.get("/")
        self.assertContains(cover, "VISCANE")
        self.assertContains(cover, "mobile-cover-logo")
        self.assertContains(cover, "/auth?mode=login&amp;cover=done")
        self.assertNotContains(cover, "Continue as Farmer")
        self.assertNotContains(cover, "Admin Portal")
        self.assertContains(client.get("/auth?mode=login"), "mobile-cover-logo")
        self.assertContains(client.get("/auth?mode=login&cover=done"), 'id="login-btn"')
        self.assertEqual(client.get("/admin-login").status_code, 403)
        self.assertContains(self.client.get("/"), "Admin Portal")

        session = client.session
        session["user_id"] = self.farmer.pk
        session.save()
        self.assertContains(client.get("/"), 'href="/homepage"')

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
        self.assertContains(news, '/static/images/sra-equipment-upgrades.jpg')
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

    def test_hiligaynon_scan_instructions_and_tutorial_catalog(self):
        client = Client(HTTP_USER_AGENT="Android ViscaneFarmer/1.0")
        session = client.session
        session["user_id"] = self.farmer.pk
        session.save()
        client.post("/i18n/setlang/", {"language": "hil", "next": "/scan/new"})
        scan = client.get("/scan/new")
        self.assertContains(scan, "Pilia ang hulagway sa imo telepono")
        self.assertContains(scan, "Siguruhon nga maathag ang puno sang tubo")
        self.assertContains(scan, "Gamita ang kamera")
        dashboard = client.get("/homepage")
        self.assertContains(dashboard, "Pangitaa ang mga gamit sa Menu")
        self.assertContains(dashboard, 'farmer-tutorial.js')

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

    @override_settings(VISCANE_OFFLINE=True, FARMER_ONLY=True)
    def test_mobile_registration_and_login_render_csrf_and_work(self):
        client = Client(
            enforce_csrf_checks=True,
            HTTP_USER_AGENT="Android ViscaneFarmer/1.0",
        )
        registration = client.get("/auth?mode=register&cover=done")
        self.assertEqual(registration.status_code, 200)
        self.assertContains(registration, 'name="csrfmiddlewaretoken"')
        csrf_token = client.cookies["csrftoken"].value

        created = client.post("/auth?mode=register", {
            "csrfmiddlewaretoken": csrf_token,
            "fullname": "Offline Farmer",
            "email": "offline-farmer@example.invalid",
            "phone": "09123456780",
            "password": "Offline-test-123!",
            "confirm_password": "Offline-test-123!",
            "province": "Negros Occidental",
            "municipality": "Isabela",
            "barangay": "Amin",
        })
        self.assertEqual(created.status_code, 302)
        self.assertEqual(created["Location"], "/auth/register-success")
        self.assertEqual(client.session["user_id"], User.objects.get(email="offline-farmer@example.invalid").pk)
        self.assertEqual(client.get(created["Location"]).status_code, 200)
        home_after_registration = client.get("/homepage")
        self.assertEqual(home_after_registration.status_code, 200)
        self.assertContains(home_after_registration, "Farmer Dashboard")

        client.get("/logout")
        login_form = client.get("/auth?mode=login&cover=done")
        self.assertEqual(login_form.status_code, 200)
        self.assertNotContains(login_form, "unpkg.com")
        login_token = client.cookies["csrftoken"].value
        logged_in = client.post("/auth?mode=login", {
            "csrfmiddlewaretoken": login_token,
            "email": "offline-farmer@example.invalid",
            "password": "Offline-test-123!",
        })
        self.assertEqual(logged_in.status_code, 302)
        self.assertEqual(logged_in["Location"], "/homepage")
        self.assertIn("user_id", client.session)
        home_after_login = client.get(logged_in["Location"])
        self.assertEqual(home_after_login.status_code, 200)
        self.assertContains(home_after_login, "Farmer Dashboard")

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
