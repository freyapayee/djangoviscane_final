"""Execution checks using Django's disposable test database and fake API responses."""
import json
import tempfile
from io import BytesIO
from PIL import Image
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import Admin, AgronomicLog, CvScanUpload, Feedback, Notification, Scan, User


def prediction_test_image():
    output = BytesIO()
    Image.new("RGB", (8, 8), "green").save(output, format="JPEG")
    return SimpleUploadedFile("test.jpg", output.getvalue(), content_type="image/jpeg")


class ExecutionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(fullname='Execution Farmer', email='farmer@example.invalid',
                                       phone='09123456789', password=make_password('Local-test-123!'))
        cls.admin = Admin.objects.create(username='execution-admin', email='admin@example.invalid',
                                         role='superadmin', password_hash=make_password('Local-test-123!'))

    def login_farmer(self):
        self.client.get('/auth')
        response = self.client.post('/auth', {'email': self.user.email, 'password': 'Local-test-123!',
            'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['user_id'], self.user.pk)

    def login_admin(self):
        self.client.get('/superadmin-login')
        response = self.client.post('/superadmin-login', {'identifier': self.admin.username,
            'password': 'Local-test-123!', 'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['admin_id'], self.admin.pk)

    def test_public_pages(self):
        for route in ['/', '/admin-access', '/auth', '/auth?mode=register', '/admin-login',
                      '/superadmin-login']:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)

    def test_registration_login_logout(self):
        response = self.client.post('/auth?mode=register', {'fullname': 'New Farmer',
            'email': 'new@example.invalid', 'phone': '09123456789',
            'password': 'Local-test-123!', 'confirm_password': 'Local-test-123!'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='new@example.invalid').exists())
        self.client.get('/logout')
        self.assertNotIn('user_id', self.client.session)
        self.login_farmer()

    def test_protected_pages_require_login(self):
        for route in ['/homepage', '/farmer/settings', '/admin', '/superadmin',
                      '/admin-register', '/superadmin-register', '/admin-reset']:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 302)

    def test_inactive_farmer_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        self.client.post('/auth', {'email': self.user.email, 'password': 'Local-test-123!'})
        self.assertNotIn('user_id', self.client.session)

    def test_farmer_pages(self):
        self.login_farmer()
        for route in ['/homepage', '/farmer/recommendations', '/farmer/agronomic-logs',
                      '/farmer/settings', '/auth/register-success', '/scan/new']:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)

    def test_admin_pages_and_export(self):
        self.login_admin()
        for route in ['/admin', '/admin/farmers', '/admin/monitoring', '/admin/models', '/admin/reports',
                      '/admin/communications', '/superadmin', '/superadmin/settings',
                      '/superadmin/reports', '/superadmin/audit',
                      '/admin-register', '/superadmin-register', '/admin-reset',
                      f'/superadmin/users/{self.user.pk}', f'/admin/farmers/{self.user.pk}/edit']:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        response = self.client.get('/superadmin/reports/download')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])

        response = self.client.get('/admin/models')
        self.assertContains(response, 'Production model')
        self.assertContains(response, 'href="/superadmin/settings"')
        self.assertEqual(self.client.post('/admin/models').status_code, 405)

    def test_admin_intelligence_filters_export_and_secure_communications(self):
        import re

        AgronomicLog.objects.create(user=self.user, variety='VMC 84-524', hectares='2',
                                    predicted_lkg_tc=2.5, predicted_tc_ha=65.0,
                                    predicted_lkg=325.0, rssi_infected='No')
        self.login_admin()

        monitoring = self.client.get('/admin/monitoring?search=Execution&status=completed')
        self.assertContains(monitoring, 'Prediction Logs')
        self.assertContains(monitoring, 'Execution Farmer')
        self.assertContains(monitoring, 'Completed')

        reports = self.client.get('/admin/reports?municipality=Unspecified')
        self.assertContains(reports, 'Farm Performance')
        export = self.client.get('/admin/reports?download=csv')
        self.assertEqual(export.status_code, 200)
        self.assertIn('text/csv', export['Content-Type'])
        self.assertIn('Execution Farmer', export.content.decode())

        self.client = Client(enforce_csrf_checks=True)
        self.login_admin()
        communications = self.client.get('/admin/communications')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', communications.content.decode()).group(1)
        response = self.client.post('/admin/communications', {
            'csrfmiddlewaretoken': token,
            'title': 'Field update',
            'message': 'Please review the latest field guidance.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.filter(title='Field update').count(), 1)

    def test_farmer_scan_validation_and_insert(self):
        self.login_farmer()
        values = {'plot_name': 'Test plot', 'grade': 'A', 'maturity_pct': '101', 'status': 'ready'}
        self.client.post('/scan/new', values)
        self.assertEqual(Scan.objects.count(), 0)
        values['maturity_pct'] = '85'
        self.assertEqual(self.client.post('/scan/new', values).status_code, 302)
        self.assertEqual(Scan.objects.get().maturity_pct, 85)

    def test_ai_scan_assessment_is_server_locked(self):
        self.login_farmer()
        session = self.client.session
        session['latest_cv_context'] = {
            'variety': 'VMC 84-524',
            'maturity_status': 'MATURE',
            'confidence': 0.972,
        }
        session.save()
        response = self.client.post('/scan/new', {
            'plot_name': 'AI Plot',
            'ai_prediction_applied': '1',
            'maturity_pct': '1',
            'grade': 'C',
            'status': 'monitor',
        })
        self.assertEqual(response.status_code, 302)
        scan = Scan.objects.get(plot_name='AI Plot')
        self.assertEqual(scan.maturity_pct, 85)
        self.assertEqual(scan.grade, 'A')
        self.assertEqual(scan.status, 'ready')

    def test_calculation_and_feedback(self):
        self.login_farmer()
        response = self.client.get('/calculate')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/homepage#calc-form')
        self.assertEqual(AgronomicLog.objects.count(), 0)
        response = self.client.post('/calculate', {'variety': 'VMC 84-524'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AgronomicLog.objects.count(), 0)
        response = self.client.post('/calculate', {'variety': 'VMC 84-524', 'hectares': '1',
            'plowing_count': '1', 'weeding_count': '2', 'fertilizer_count': '3',
            'ratoon_stage': '1', 'rssi_infected': 'no'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(AgronomicLog.objects.get().predicted_lkg)
        self.client.post('/farmer/feedback', {'feedback_message': 'Execution test feedback'})
        self.assertEqual(Feedback.objects.count(), 1)

    def test_admin_create_search_edit_and_status(self):
        self.login_admin()
        self.client.post('/admin/farmers', {'action': 'create', 'fullname': 'Managed Farmer',
            'email': 'managed@example.invalid', 'phone': '09123456789', 'password': 'Local-test-123!'})
        user = User.objects.get(email='managed@example.invalid')
        self.assertContains(self.client.get('/admin/farmers?search=Managed'), 'Managed Farmer')
        self.client.post(f'/admin/farmers/{user.pk}/edit', {'fullname': 'Updated Farmer',
            'email': user.email, 'phone': user.phone})
        user.refresh_from_db()
        self.assertEqual(user.fullname, 'Updated Farmer')
        for action, expected in [('deactivate', False), ('activate', True)]:
            self.client.post('/admin/farmers', {'action': action, 'user_id': user.pk})
            user.refresh_from_db()
            self.assertEqual(user.is_active, expected)

    def test_admin_farmer_directory_pagination_empty_state_and_delete(self):
        self.login_admin()
        User.objects.bulk_create([
            User(fullname=f'Pagination Farmer {index:02d}', email=f'page-{index}@example.invalid',
                 phone=f'09123456{index:03d}', password='unused')
            for index in range(12)
        ])

        response = self.client.get('/admin/farmers')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total Farmers')
        self.assertContains(response, 'Active Accounts')
        self.assertContains(response, 'Deactivated')
        self.assertContains(response, 'aria-label="Farmer account pages"')
        self.assertContains(response, 'data-action="reset"')
        self.assertContains(response, 'data-action="deactivate"')
        self.assertContains(response, 'data-action="delete"')

        second_page = self.client.get('/admin/farmers?page=2')
        self.assertEqual(second_page.status_code, 200)
        self.assertContains(second_page, 'Pagination Farmer 01')

        target = User.objects.get(email='page-1@example.invalid')
        response = self.client.post('/admin/farmers', {'action': 'delete', 'user_id': target.pk})
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertTrue(target.is_archived)
        self.assertFalse(target.is_active)

        empty = self.client.get('/admin/farmers?search=does-not-exist')
        self.assertContains(empty, 'No farmer accounts found')
        self.assertContains(empty, 'Clear Search')

    def test_admin_forms_work_with_csrf_enforced(self):
        import re
        self.client = Client(enforce_csrf_checks=True)
        self.login_admin()
        response = self.client.get('/admin/farmers')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)
        response = self.client.post('/admin/farmers', {'csrfmiddlewaretoken': token, 'action': 'create',
            'fullname': 'CSRF Farmer', 'email': 'csrf@example.invalid', 'phone': '09123456789',
            'password': 'Local-test-123!'})
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='csrf@example.invalid')
        response = self.client.get(f'/admin/farmers/{user.pk}/edit')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)
        response = self.client.post(f'/admin/farmers/{user.pk}/edit', {'csrfmiddlewaretoken': token,
            'fullname': 'CSRF Updated', 'email': user.email, 'phone': user.phone})
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.fullname, 'CSRF Updated')

    def test_upload_missing_file_and_invalid_top_k(self):
        self.login_farmer()
        self.assertEqual(self.client.post('/api/scan/predict').status_code, 400)
        response = self.client.post('/api/scan/predict?top_k=bad',
            {'file': SimpleUploadedFile('test.jpg', b'test', content_type='image/jpeg')})
        self.assertEqual(response.status_code, 400)

    def test_prediction_contract_and_persistence_with_mock_service(self):
        self.login_farmer()
        payload = {'variety': 'VMC 84-524', 'maturity_status': 'MATURE', 'confidence': .9}
        with tempfile.TemporaryDirectory() as folder, override_settings(PRIVATE_UPLOAD_ROOT=Path(folder)):
            with patch('core.views.request_prediction_service', return_value=((json.dumps(payload).encode(), 200), None, None)):
                response = self.client.post('/api/scan/predict',
                    {'file': prediction_test_image()})
            self.assertEqual(response.status_code, 200)
            upload = CvScanUpload.objects.get()
            self.assertTrue((Path(folder) / upload.image_path).exists())
            self.assertIn('latest_cv_context', self.client.session)

    def test_prediction_bad_json_and_unreachable(self):
        self.login_farmer()
        cases = [(((b'not-json', 200), None, None), 502),
                 ((None, {'error': 'Prediction service is unreachable.'}, 502), 502)]
        for result, expected in cases:
            with self.subTest(result=result), patch('core.views.request_prediction_service', return_value=result):
                response = self.client.post('/api/scan/predict', {'file': prediction_test_image()})
                self.assertEqual(response.status_code, expected)

    def test_user_cannot_delete_another_users_upload(self):
        other = User.objects.create(fullname='Other', email='other@example.invalid', phone='0', password='unused')
        upload = CvScanUpload.objects.create(user=other, image_path='nonexistent-test-image.jpg')
        self.login_farmer()
        self.client.post(f'/farmer/cv-upload/{upload.pk}/delete')
        self.assertTrue(CvScanUpload.objects.filter(pk=upload.pk).exists())

    def test_owner_can_delete_upload(self):
        self.login_farmer()
        with tempfile.TemporaryDirectory() as folder, patch('core.views.get_static_root', return_value=Path(folder)):
            (Path(folder) / 'test.jpg').write_bytes(b'test')
            upload = CvScanUpload.objects.create(user=self.user, image_path='test.jpg')
            self.client.post(f'/farmer/cv-upload/{upload.pk}/delete')
            self.assertFalse(CvScanUpload.objects.filter(pk=upload.pk).exists())
            self.assertFalse((Path(folder) / 'test.jpg').exists())

    def test_deleted_picture_does_not_reappear_on_another_recent_scan(self):
        self.login_farmer()
        older_upload = CvScanUpload.objects.create(user=self.user, image_path='older.jpg', original_filename='older.jpg')
        older_scan = Scan.objects.create(user=self.user, cv_upload=older_upload, plot_name='Older plot', grade='A', maturity_pct=85)
        newer_upload = CvScanUpload.objects.create(user=self.user, image_path='newer.jpg', original_filename='newer.jpg')
        CvScanUpload.objects.create(user=self.user, image_path='duplicate.jpg', original_filename='newer.jpg')
        newer_scan = Scan.objects.create(user=self.user, cv_upload=newer_upload, plot_name='Newer plot', grade='A', maturity_pct=85)
        with tempfile.TemporaryDirectory() as folder, patch('core.views.get_static_root', return_value=Path(folder)):
            response = self.client.post(f'/farmer/cv-upload/{newer_upload.pk}/delete', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('#recent-scans', response.redirect_chain[-1][0])
        self.assertContains(response, 'id="scan-feedback-toast"')
        self.assertNotContains(response, '<div class="form-success">Picture removed')
        newer_scan.refresh_from_db()
        older_scan.refresh_from_db()
        self.assertIsNone(newer_scan.cv_upload)
        self.assertTrue(newer_scan.hidden_from_recent)
        self.assertEqual(older_scan.cv_upload_id, older_upload.pk)
        recent_html = response.content.decode().split('<section id="recent-scans"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('Newer plot', recent_html)
        self.assertIn('Older plot', recent_html)
        self.assertEqual(recent_html.count('<strong>Uploaded:</strong> older.jpg'), 1)
        gallery_html = response.content.decode().split('<div id="scan-gallery" class="panel scan-gallery-block">', 1)[1].split('</section>', 1)[0]
        self.assertIn('<strong class="scan-gallery-plot">Older plot</strong>', gallery_html)
        self.assertIn(f'/farmer/cv-upload/{older_upload.pk}/image', gallery_html)
        self.assertNotIn('Newer plot', gallery_html)
        self.assertNotContains(response, 'newer.jpg')
        self.assertNotContains(response, 'duplicate.jpg')
        with tempfile.TemporaryDirectory() as folder, patch('core.views.get_static_root', return_value=Path(folder)):
            empty_response = self.client.post(f'/farmer/cv-upload/{older_upload.pk}/delete', follow=True)
        self.assertContains(empty_response, 'No recent scans to show.')
        self.assertContains(empty_response, 'No uploaded scans yet.')
        self.assertNotContains(empty_response, 'Computer vision upload')

    def test_scan_gallery_is_paginated_without_losing_older_scans(self):
        self.login_farmer()
        for index in range(5):
            upload = CvScanUpload.objects.create(user=self.user, image_path=f'gallery-{index}.jpg')
            Scan.objects.create(user=self.user, cv_upload=upload, plot_name=f'Gallery plot {index}',
                                grade='A', maturity_pct=85)

        first = self.client.get('/homepage').content.decode().split('<div id="scan-gallery"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(first.count('<figure class="scan-gallery-item">'), 4)
        self.assertIn('Gallery plot 4', first)
        self.assertNotIn('Gallery plot 0', first)
        self.assertIn('?gallery_page=2&recent_page=1#scan-gallery', first)

        second = self.client.get('/homepage?gallery_page=2').content.decode().split('<div id="scan-gallery"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(second.count('<figure class="scan-gallery-item">'), 1)
        self.assertIn('Gallery plot 0', second)
        self.assertNotIn('Gallery plot 4', second)

        recent_first = self.client.get('/homepage?gallery_page=2').content.decode().split('<section id="recent-scans"', 1)[1].split('<div id="scan-gallery"', 1)[0]
        self.assertEqual(recent_first.count('<div class="recent-item">'), 4)
        self.assertIn('?recent_page=2&gallery_page=2#recent-scans', recent_first)
        recent_second = self.client.get('/homepage?recent_page=2&gallery_page=2').content.decode().split('<section id="recent-scans"', 1)[1].split('<div id="scan-gallery"', 1)[0]
        self.assertEqual(recent_second.count('<div class="recent-item">'), 1)
        self.assertIn('Gallery plot 0', recent_second)
        self.assertNotIn('Gallery plot 4', recent_second)
        self.assertIn('?recent_page=1&gallery_page=2#recent-scans', recent_second)

    def test_get_cannot_delete_owned_upload(self):
        upload = CvScanUpload.objects.create(user=self.user, image_path='test.jpg')
        self.login_farmer()
        self.assertEqual(self.client.get(f'/farmer/cv-upload/{upload.pk}/delete').status_code, 405)
        self.assertTrue(CvScanUpload.objects.filter(pk=upload.pk).exists())

    def test_anonymous_cannot_create_admin_or_reset_password(self):
        original_hash = self.admin.password_hash
        create_payload = {'username': 'untrusted', 'email': 'untrusted@example.invalid',
                          'password': 'Local-test-123!', 'confirm_password': 'Local-test-123!'}
        for route in ['/admin-register', '/superadmin-register']:
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route, create_payload).status_code, 302)
        self.assertFalse(Admin.objects.filter(username='untrusted').exists())
        response = self.client.post('/admin-reset', {'identifier': self.admin.username,
            'email': self.admin.email, 'password': 'Changed-test-123!',
            'confirm_password': 'Changed-test-123!'})
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.password_hash, original_hash)

    def test_superadmin_can_create_admin_and_reset_password_with_csrf(self):
        import re
        self.client = Client(enforce_csrf_checks=True)
        self.login_admin()
        response = self.client.get('/admin-register')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)
        response = self.client.post('/admin-register', {'csrfmiddlewaretoken': token,
            'username': 'managed-admin', 'email': 'managed-admin@example.invalid', 'role': 'admin',
            'password': 'Local-test-123!', 'confirm_password': 'Local-test-123!'})
        self.assertEqual(response.status_code, 302)
        managed = Admin.objects.get(username='managed-admin')
        response = self.client.get('/admin-reset')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)
        response = self.client.post('/admin-reset', {'csrfmiddlewaretoken': token,
            'identifier': managed.username, 'email': managed.email, 'password': 'Changed-test-123!',
            'confirm_password': 'Changed-test-123!'})
        self.assertEqual(response.status_code, 200)
        managed.refresh_from_db()
        from django.contrib.auth.hashers import check_password
        self.assertTrue(check_password('Changed-test-123!', managed.password_hash))

    def test_legacy_scanner_uses_working_prediction_endpoint(self):
        self.login_farmer()
        response = self.client.get('/scan/new')
        self.assertContains(response, '/api/scan/predict?top_k=3')
        self.assertNotContains(response, '/analyze_stalk')
