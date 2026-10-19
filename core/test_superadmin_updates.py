from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Admin, AgronomicLog, AuditLog, CvScanUpload, Scan, User


class SuperadminUpdatesTests(TestCase):
    def setUp(self):
        self.admin = Admin.objects.create(username="super", email="super@example.invalid", password_hash="unused", role="superadmin")
        self.farmer = User.objects.create(fullname="Test Farmer", email="farmer@example.invalid", phone="123", password="unused")
        session = self.client.session
        session["admin_id"] = self.admin.pk
        session.save()

    def test_management_moved_and_pages_render(self):
        overview = self.client.get('/superadmin')
        self.assertNotContains(overview, 'Superadmin Modules')
        self.assertNotContains(overview, 'Register Admin or Superadmin')
        self.assertLess(overview.content.index(b'Recent Predictions'), overview.content.index(b'System Health'))
        self.assertContains(self.client.get('/superadmin/admins'), 'Register Admin or Superadmin')
        self.assertContains(self.client.get('/superadmin/governance'), 'User Governance menu')
        self.assertContains(self.client.get('/superadmin/scan-gallery'), 'Sugarcane Scan Gallery')
        response = self.client.post('/superadmin/admins/create', {})
        self.assertTrue(response.url.startswith('/superadmin/admins?'))

    def test_photo_delete_requires_superadmin_post_and_reason(self):
        with TemporaryDirectory() as directory, override_settings(PRIVATE_UPLOAD_ROOT=Path(directory)):
            path = Path(directory) / 'private' / 'photo.jpg'
            path.parent.mkdir()
            path.write_bytes(b'test photo')
            upload = CvScanUpload.objects.create(user=self.farmer, image_path='private/photo.jpg')
            scan = Scan.objects.create(user=self.farmer, cv_upload=upload, plot_name='Plot', grade='A', maturity_pct=80)
            log = AgronomicLog.objects.create(user=self.farmer, scan=scan, predicted_lkg=100)
            url = f'/superadmin/scan-gallery/{upload.pk}/delete'
            self.assertEqual(self.client.get(url).status_code, 405)
            self.client.post(url, {'reason': '   '})
            self.assertTrue(path.exists())
            self.assertTrue(CvScanUpload.objects.filter(pk=upload.pk).exists())
            self.admin.role = 'admin'
            self.admin.save()
            self.client.post(url, {'reason': 'Unnecessary photo'})
            self.assertTrue(path.exists())
            self.admin.role = 'superadmin'
            self.admin.save()
            self.assertEqual(self.client.get(f'/farmer/cv-upload/{upload.pk}/image').status_code, 200)
            self.assertContains(self.client.get('/superadmin/scan-gallery'), 'Reason for deleting')
            self.client.post(url, {'reason': 'Unnecessary photo'})
            self.assertFalse(path.exists())
            self.assertFalse(CvScanUpload.objects.filter(pk=upload.pk).exists())
            scan.refresh_from_db()
            self.assertIsNone(scan.cv_upload_id)
            self.assertTrue(AgronomicLog.objects.filter(pk=log.pk).exists())
            self.assertTrue(AuditLog.objects.filter(user_id=self.admin.pk, action__contains='Reason: Unnecessary photo').exists())

    def test_compliance_calendar_periods(self):
        for day, month, year, action in [(20,10,2026,'today-entry'), (19,10,2026,'week-entry'), (1,10,2026,'month-entry'), (1,1,2026,'year-entry'), (31,12,2025,'outside-entry')]:
            log = AuditLog.objects.create(action=action)
            AuditLog.objects.filter(pk=log.pk).update(timestamp=timezone.make_aware(datetime(year,month,day,12)))
        expected = {'daily':1, 'weekly':2, 'monthly':3, 'yearly':4}
        for period, count in expected.items():
            response = self.client.get('/superadmin/audit', {'period':period,'date':'2026-10-20'})
            for index, action in enumerate(['today-entry','week-entry','month-entry','year-entry']):
                if index < count:
                    self.assertContains(response, action)
                else:
                    self.assertNotContains(response, action)
            self.assertNotContains(response, 'outside-entry')
        self.assertEqual(self.client.get('/superadmin/audit?period=bad&date=bad').status_code, 200)

    def test_yield_daily_and_weekly_on_both_sides(self):
        log = AgronomicLog.objects.create(user=self.farmer, predicted_lkg_tc=2, predicted_tc_ha=60, predicted_lkg=120)
        AgronomicLog.objects.filter(pk=log.pk).update(created_at=timezone.make_aware(datetime(2026,10,20,12)))
        for base in ['/admin', '/superadmin']:
            self.assertContains(self.client.get(base+'/variety-analytics?year=2026&month=10'), 'Daily Yield')
            data = self.client.get(base+'/api/variety-analytics?year=2026&month=10').json()
            self.assertEqual(data['daily_rows'][0]['label'], '2026-10-20')
            self.assertEqual(data['weekly_rows'][0]['label'], '2026-W43')
            self.assertEqual(data['weekly_rows'][0]['total_lkg'], 120)

    def test_report_export_requires_valid_period(self):
        for params in [{}, {'period': 'date', 'start': 'invalid'}, {'period': 'month', 'start': '2026-13'}, {'period': 'year', 'start': '2027', 'end': '2026'}, {'period': 'date', 'start': '2026-02-30'}]:
            self.assertEqual(self.client.get('/superadmin/reports/download', params).status_code, 400)

    def test_report_preview_and_csv_share_inclusive_ranges(self):
        for year, month, day, variety in [(2025,12,31,'Previous'), (2026,1,1,'January'), (2026,10,20,'October'), (2027,1,1,'Next')]:
            log = AgronomicLog.objects.create(user=self.farmer, variety=variety, predicted_lkg=100)
            AgronomicLog.objects.filter(pk=log.pk).update(created_at=timezone.make_aware(datetime(year,month,day,0,30)))
        cases = [
            ({'period':'date', 'start':'2026-10-20'}, ['October']),
            ({'period':'month', 'start':'2026-01', 'end':'2026-10'}, ['January','October']),
            ({'period':'year', 'start':'2026'}, ['January','October']),
            ({'period':'year', 'start':'2025','end':'2026'}, ['Previous','January','October']),
        ]
        for params, expected in cases:
            response = self.client.get('/superadmin/reports/download', params)
            self.assertEqual(response.status_code, 200)
            import csv
            from io import StringIO
            rows = list(csv.DictReader(StringIO(response.content.decode())))
            self.assertCountEqual([row['Variety'] for row in rows], expected)
            preview = self.client.get('/superadmin/reports', params)
            self.assertEqual(preview.status_code, 200)
            for variety in expected:
                self.assertContains(preview, f'<td>{variety}</td>', html=True)
            for variety in set(['Previous','January','October','Next']) - set(expected):
                self.assertNotContains(preview, f'<td>{variety}</td>', html=True)
        self.assertContains(self.client.get('/superadmin/reports'), 'Filter by dates')

    def test_governance_shows_saved_deactivation_reason(self):
        self.farmer.is_active = False
        self.farmer.restriction_reason = 'Duplicate registration; verify ownership.'
        self.farmer.save()
        self.assertContains(self.client.get('/superadmin/governance'), self.farmer.restriction_reason)
        self.farmer.restriction_reason = ''
        self.farmer.save()
        self.assertContains(self.client.get('/superadmin/governance'), 'No reason recorded.')
