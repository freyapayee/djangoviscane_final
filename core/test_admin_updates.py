from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from .models import Admin, AgronomicLog, Feedback, FeedbackReply, User


class AdminUpdatesTests(TestCase):
    def setUp(self):
        self.admin = Admin.objects.create(username="report-admin", email="report-admin@example.invalid", password_hash="unused")
        self.alex = User.objects.create(fullname="Alex Farmer", email="alex@example.invalid", phone="09111111111", password="unused", barangay="Amin")
        self.betty = User.objects.create(fullname="Betty Farmer", email="betty@example.invalid", phone="09222222222", password="unused", barangay="Banogbanog")
        session = self.client.session
        session["admin_id"] = self.admin.pk
        session.save()

    def test_csv_requires_period_and_respects_day_and_barangay(self):
        for farmer, day in ((self.alex, 17), (self.betty, 18)):
            log = AgronomicLog.objects.create(user=farmer, predicted_lkg=100)
            AgronomicLog.objects.filter(pk=log.pk).update(created_at=timezone.make_aware(datetime(2026, 10, day, 12)))
        self.assertEqual(self.client.get("/admin/reports?download=csv").status_code, 400)
        csv_response = self.client.get("/admin/reports?download=csv&year=2026&month=10&day=17")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Alex Farmer", csv_response.content.decode())
        self.assertNotIn("Betty Farmer", csv_response.content.decode())
        csv_response = self.client.get("/admin/reports?download=csv&year=2026&month=10&barangay=Banogbanog")
        self.assertNotIn("Alex Farmer", csv_response.content.decode())
        self.assertIn("Betty Farmer", csv_response.content.decode())

    def test_hold_and_deactivation_require_reason(self):
        self.client.post("/admin/farmers", {"action": "hold", "user_id": self.alex.pk})
        self.alex.refresh_from_db()
        self.assertTrue(self.alex.is_active)
        self.client.post("/admin/farmers", {"action": "hold", "user_id": self.alex.pk, "reason": "Verify account details"})
        self.alex.refresh_from_db()
        self.assertFalse(self.alex.is_active)
        self.assertEqual(self.alex.restriction_type, "hold")
        self.assertEqual(self.alex.restriction_reason, "Verify account details")
        self.assertContains(self.client.get("/admin/farmers"), "Verify account details")
        self.client.post("/admin/farmers", {"action": "activate", "user_id": self.alex.pk})
        self.alex.refresh_from_db()
        self.assertTrue(self.alex.is_active)
        self.assertEqual(self.alex.restriction_reason, "")

    def test_admin_reply_appears_for_its_farmer_only(self):
        feedback = Feedback.objects.create(user_id=self.alex.pk, message="Need help with a scan")
        self.client.post("/admin/communications", {"action": "reply", "feedback_id": feedback.pk, "reply_message": "Please try again in daylight."})
        self.assertEqual(FeedbackReply.objects.filter(feedback=feedback).count(), 1)
        self.assertContains(self.client.get("/admin/communications"), "Farmer Inbox")
        session = self.client.session
        session.pop("admin_id")
        session["user_id"] = self.alex.pk
        session.save()
        self.assertContains(self.client.get("/farmer/news"), "Please try again in daylight.")
        session = self.client.session
        session["user_id"] = self.betty.pk
        session.save()
        self.assertNotContains(self.client.get("/farmer/news"), "Please try again in daylight.")

    def test_yield_analytics_has_daily_and_weekly_rows(self):
        log = AgronomicLog.objects.create(user=self.alex, predicted_lkg_tc=2, predicted_tc_ha=60, predicted_lkg=120)
        AgronomicLog.objects.filter(pk=log.pk).update(created_at=timezone.make_aware(datetime(2026, 10, 17, 12)))
        response = self.client.get("/admin/variety-analytics?year=2026&month=10")
        self.assertContains(response, "Daily Yield")
        self.assertContains(response, "Weekly Yield")
        self.assertContains(response, "2026-10-17")
        self.assertContains(response, "2026-W42")
