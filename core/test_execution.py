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

from .models import Admin, AgronomicLog, AuditLog, CvScanUpload, Feedback, Notification, Scan, User
from .services import normalize_cv_variety_name


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
        for route in ['/homepage', '/farmer/settings', '/admin', '/superadmin', '/superadmin/scan-gallery',
                      '/admin-reset']:
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

    def test_farmer_settings_password_disclosure_and_signout(self):
        self.login_farmer()
        response = self.client.get('/farmer/settings')
        html = response.content.decode()
        self.assertIn('<details class="settings-password-disclosure">', html)
        self.assertLess(html.index('class="panel settings-profile"'),
                        html.index('class="settings-password-disclosure"'))
        self.assertLess(html.index('class="settings-password-disclosure"'),
                        html.index('class="settings-signout-button"'))
        self.assertIn('href="/logout"', html)

        response = self.client.post('/farmer/settings', {
            'action': 'update_password',
            'current_password': 'incorrect',
            'new_password': 'Updated-test-123!',
            'confirm_password': 'Updated-test-123!',
        })
        self.assertContains(response, '<details class="settings-password-disclosure" open>')
        self.assertContains(response, 'Current password is incorrect.')

    def test_farmer_profile_photo_upload_access_and_removal(self):
        self.login_farmer()
        profile = self.client.get('/farmer/settings')
        self.assertContains(profile, 'images/default-farmer-avatar.svg')
        self.assertContains(profile, 'class="profile-edit-button"')
        self.assertContains(profile, 'enctype="multipart/form-data"')
        with tempfile.TemporaryDirectory() as folder, override_settings(PRIVATE_UPLOAD_ROOT=Path(folder)):
            fields = {'action': 'update_profile', 'email': self.user.email, 'phone': self.user.phone,
                      'province': 'Negros Occidental', 'municipality': 'Isabela', 'barangay': 'Amin'}
            upload = self.client.post('/farmer/settings', {**fields, 'profile_photo': prediction_test_image()})
            self.assertContains(upload, 'Profile updated successfully.')
            self.user.refresh_from_db()
            photo_path = Path(folder) / 'profile_photos' / self.user.profile_photo_path
            self.assertTrue(photo_path.is_file())
            with Image.open(photo_path) as photo:
                self.assertEqual(photo.size, (512, 512))
                self.assertEqual(photo.format, 'JPEG')
            photo_url = f'/farmer/profile-photo/{self.user.pk}'
            self.assertContains(upload, photo_url)
            served = self.client.get(photo_url)
            self.assertEqual(served.status_code, 200)
            self.assertEqual(served['Content-Type'], 'image/jpeg')
            self.assertEqual(served['Cache-Control'], 'private, no-store')
            self.assertEqual(Client().get(photo_url).status_code, 404)
            other = User.objects.create(fullname='Other Farmer', email='other-photo@example.invalid',
                                        phone='09111111111', password=make_password('Local-test-123!'))
            other_client = Client()
            session = other_client.session
            session['user_id'] = other.pk
            session.save()
            self.assertEqual(other_client.get(photo_url).status_code, 404)

            removed = self.client.post('/farmer/settings', {**fields, 'remove_profile_photo': '1'})
            self.assertContains(removed, 'images/default-farmer-avatar.svg')
            self.user.refresh_from_db()
            self.assertEqual(self.user.profile_photo_path, '')
            self.assertFalse(photo_path.exists())

    def test_farmer_profile_photo_rejects_invalid_file(self):
        self.login_farmer()
        fields = {'action': 'update_profile', 'email': self.user.email, 'phone': self.user.phone,
                  'province': 'Negros Occidental', 'municipality': 'Isabela', 'barangay': 'Amin'}
        response = self.client.post('/farmer/settings', {
            **fields, 'profile_photo': SimpleUploadedFile('not-an-image.jpg', b'bad data', content_type='image/jpeg')})
        self.assertContains(response, 'Choose a valid JPEG, PNG or WebP profile photo.')
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_photo_path, '')

    def test_admin_pages_and_export(self):
        self.login_admin()
        for route in ['/admin', '/admin/farmers', '/admin/monitoring', '/admin/models', '/admin/reports',
                      '/admin/communications', '/superadmin', '/superadmin/settings',
                      '/superadmin/reports', '/superadmin/audit', '/superadmin/scan-gallery',
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

    def test_admin_dashboard_uses_recorded_logs_and_filters_users(self):
        inactive = User.objects.create(fullname='Inactive Farmer', email='inactive@example.invalid',
                                       phone='09999999999', password=make_password('Local-test-123!'),
                                       is_active=False)
        self.login_admin()
        response = self.client.get('/admin')
        self.assertContains(response, 'No system activity has been recorded yet.')
        self.assertNotContains(response, 'Uptime 99.9%')
        self.assertNotContains(response, 'Database Backup')
        self.assertContains(response, 'class="admin-user-filter"')

        AuditLog.objects.create(action='Admin created farmer account: Real Farmer')
        response = self.client.get('/admin?user_search=Inactive&user_status=inactive')
        self.assertContains(response, 'Admin created farmer account: Real Farmer')
        self.assertContains(response, 'Inactive Farmer')
        self.assertNotContains(response, 'Execution Farmer')
        self.assertContains(response, 'class="admin-user-filter" open')
        self.assertContains(response, 'No scans yet')

    def test_superadmin_combined_cv_result_uses_report(self):
        self.login_admin()
        self.assertContains(self.client.get('/superadmin'), '97.72%')
        with tempfile.TemporaryDirectory() as temp_dir, override_settings(BASE_DIR=Path(temp_dir)):
            response = self.client.get('/superadmin')
            self.assertContains(response, 'Combined Model Accuracy')
            self.assertContains(response, 'Result unavailable')
            self.assertNotContains(response, 'Admin Workspace')
            self.assertNotContains(response, '97.69%')
            self.assertNotContains(response, '98.18%')

            report_dir = Path(temp_dir) / 'reports'
            report_dir.mkdir()
            (report_dir / 'cv_training_results_latest.json').write_text(
                json.dumps({'combined_accuracy_pct': 91.234}), encoding='utf-8')
            response = self.client.get('/superadmin')
            self.assertContains(response, '91.23%')
            self.assertNotContains(response, 'Result unavailable')

    def test_superadmin_scan_gallery_has_its_own_page(self):
        upload = CvScanUpload.objects.create(
            user=self.user, image_path='private/cv_scans/gallery.jpg',
            original_filename='gallery.jpg', variety='VMC 84-524', maturity_status='mature')
        self.login_admin()
        overview = self.client.get('/superadmin')
        self.assertContains(overview, 'href="/superadmin/scan-gallery"')
        self.assertNotContains(overview, 'Sugarcane Scan Gallery')
        gallery = self.client.get('/superadmin/scan-gallery')
        self.assertContains(gallery, 'Sugarcane Scan Gallery')
        self.assertContains(gallery, 'VMC 84-524')
        self.assertContains(gallery, f'/farmer/cv-upload/{upload.pk}/image')

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

    def test_farmer_scan_requires_analyzed_photo(self):
        self.login_farmer()
        response = self.client.post('/scan/new', {'plot_name': 'Test plot'})
        self.assertContains(response, 'Please scan an image before continuing.')
        self.assertEqual(Scan.objects.count(), 0)

    def test_ai_scan_assessment_is_server_locked(self):
        self.login_farmer()
        session = self.client.session
        upload = CvScanUpload.objects.create(user=self.user, image_path='private/cv_scans/test.jpg', variety='VMC 84-524')
        session['latest_cv_context'] = {
            'variety': 'VMC 84-524',
            'maturity_status': 'MATURE',
            'confidence': 0.972,
            'upload_id': upload.pk,
        }
        session.save()
        response = self.client.post('/scan/new', {
            'plot_name': 'AI Plot',
            'ai_prediction_applied': '1',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/homepage#calc-form')
        scan = Scan.objects.get(plot_name='AI Plot')
        self.assertEqual(scan.maturity_pct, 85)
        self.assertEqual(scan.grade, 'A')
        self.assertEqual(scan.status, 'ready')
        self.assertEqual(scan.cv_upload, upload)
        homepage = self.client.get('/homepage')
        self.assertContains(homepage, 'const savedScanVariety = normalizeCvVariety("VMC 84-524")')
        self.assertContains(homepage, 'cvMaturityStatusInput.value = "MATURE"')
        self.assertContains(homepage, 'id="open-camera-btn"')
        self.assertNotContains(self.client.get('/scan/new'), 'name="grade"')
        self.assertNotContains(self.client.get('/scan/new'), 'name="status"')
        self.assertNotContains(self.client.get('/scan/new'), 'name="maturity_pct"')

    def test_camera_result_uses_review_and_saves_to_gallery(self):
        self.login_farmer()
        payload = {'variety': 'VMC 847', 'maturity_status': 'MATURE', 'confidence': .91}
        with tempfile.TemporaryDirectory() as folder, override_settings(PRIVATE_UPLOAD_ROOT=Path(folder)):
            with patch('core.views.request_prediction_service', return_value=((json.dumps(payload).encode(), 200), None, None)):
                result = self.client.post('/api/scan/predict', {'file': prediction_test_image()})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['prediction']['variety'], 'VMC 84-947')
            review = self.client.get('/scan/new?review=1')
            self.assertContains(review, 'VMC 84-947')
            self.assertContains(review, '91.0%')
            self.assertContains(review, 'Proceed to Agronomic Input')
            self.assertNotContains(review, 'Maturity percentage')
            save = self.client.post('/scan/new', {'plot_name': 'Camera plot', 'ai_prediction_applied': '1'})
            self.assertEqual(save['Location'], '/homepage#calc-form')
            scan = Scan.objects.get(plot_name='Camera plot')
            self.assertIsNotNone(scan.cv_upload)
            self.assertEqual(scan.cv_upload.variety, 'VMC 84-947')
            homepage = self.client.get('/homepage')
            self.assertContains(homepage, 'Camera plot')
            self.assertContains(homepage, f'/farmer/cv-upload/{scan.cv_upload_id}/image')
            self.assertContains(homepage, 'const savedScanVariety = normalizeCvVariety("VMC 84-947")')

    def test_low_confidence_scan_is_rejected_before_it_is_saved(self):
        self.login_farmer()
        with tempfile.TemporaryDirectory() as folder, override_settings(PRIVATE_UPLOAD_ROOT=Path(folder)):
            for confidence in (0.40, 0.499, 49.9):
                with self.subTest(confidence=confidence):
                    payload = {'variety': 'VMC 84-524', 'maturity_status': 'MATURE', 'confidence': confidence}
                    with patch('core.views.request_prediction_service', return_value=((json.dumps(payload).encode(), 200), None, None)):
                        response = self.client.post('/api/scan/predict', {'file': prediction_test_image()})
                    self.assertEqual(response.status_code, 422)
                    self.assertEqual(response.json()['error'], 'Invalid Image. This Image is not supported')
                    self.assertFalse(CvScanUpload.objects.exists())
                    self.assertNotIn('latest_cv_context', self.client.session)

            for confidence in (0.50, 50):
                with self.subTest(confidence=confidence):
                    payload['confidence'] = confidence
                    with patch('core.views.request_prediction_service', return_value=((json.dumps(payload).encode(), 200), None, None)):
                        response = self.client.post('/api/scan/predict', {'file': prediction_test_image()})
                    self.assertEqual(response.status_code, 200)
            self.assertEqual(CvScanUpload.objects.count(), 2)

    def test_old_low_confidence_result_cannot_be_used_for_a_scan(self):
        self.login_farmer()
        upload = CvScanUpload.objects.create(user=self.user, image_path='old-low-result.jpg', confidence=0.4)
        session = self.client.session
        session['latest_cv_context'] = {'upload_id': upload.pk, 'variety': 'VMC 84-524',
                                        'maturity_status': 'MATURE', 'confidence': 0.4}
        session.save()
        review = self.client.get('/scan/new?review=1')
        self.assertNotContains(review, '40.0%')
        self.assertNotIn('latest_cv_context', self.client.session)
        response = self.client.post('/scan/new', {'plot_name': 'Unsupported image', 'ai_prediction_applied': '1'})
        self.assertContains(response, 'Invalid Image. This Image is not supported')
        self.assertFalse(Scan.objects.filter(plot_name='Unsupported image').exists())
        session = self.client.session
        session['latest_cv_context'] = {'upload_id': upload.pk, 'variety': 'VMC 84-524',
                                        'maturity_status': 'MATURE', 'confidence': 0.4}
        session.save()
        response = self.client.post('/calculate', {'cv_prediction_applied': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('Invalid+Image.', response['Location'])
        self.assertFalse(AgronomicLog.objects.exists())

    def test_scan_classification_expands_supported_varieties(self):
        self.assertEqual(normalize_cv_variety_name('VMC 524'), 'VMC 84-524')
        self.assertEqual(normalize_cv_variety_name('vmc_524'), 'VMC 84-524')
        self.assertEqual(normalize_cv_variety_name('VMC 847'), 'VMC 84-947')
        self.assertEqual(normalize_cv_variety_name('MAURITIO'), 'MAURITIO RC888')

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
        self.assertContains(response, 'href="/farmer/recommendations"')
        self.assertContains(response, 'See Recommendations')
        self.assertIsNotNone(AgronomicLog.objects.get().predicted_lkg)
        self.client.post('/farmer/feedback', {'feedback_message': 'Execution test feedback'})
        self.assertEqual(Feedback.objects.count(), 1)

    def test_recommendation_categories_have_separate_sections(self):
        self.login_farmer()
        session = self.client.session
        session['farmer_recommendations'] = [
            {'category': 'Harvest Directives', 'title': 'Check harvest timing', 'meta': 'Harvest guidance', 'icon': 'sunny-outline', 'tag': 'Plan'},
            {'category': 'Fertilizer Guidance', 'title': 'Check fertilizer timing', 'meta': 'Fertilizer guidance', 'icon': 'flask-outline', 'tag': 'Guide'},
        ]
        session.save()
        response = self.client.get('/farmer/recommendations')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/farmer/agronomic-logs#recommendation-history"')
        self.assertContains(response, 'class="recommendation-area"', count=2)
        self.assertContains(response, 'data-tone="harvest"')
        self.assertContains(response, 'data-tone="fertilizer"')
        self.assertContains(response, 'name="sunny-outline"')
        self.assertContains(response, 'name="flask-outline"')

    def test_input_history_shows_linked_scan_and_calculation(self):
        self.login_farmer()
        upload = CvScanUpload.objects.create(user=self.user, image_path='private/cv_scans/history.jpg',
            original_filename='history.jpg', variety='VMC 84-524', maturity_status='MATURE', confidence=.91)
        scan = Scan.objects.create(user=self.user, cv_upload=upload, plot_name='North field',
            grade='A', maturity_pct=85, status='ready')
        response = self.client.post('/calculate', {'variety': 'VMC 84-524', 'hectares': '1',
            'plowing_count': '1', 'weeding_count': '2', 'fertilizer_count': '3',
            'ratoon_stage': '1', 'rssi_infected': 'no'})
        self.assertEqual(response.status_code, 200)
        log = AgronomicLog.objects.get()
        self.assertEqual(log.scan_id, scan.pk)
        self.assertTrue(log.recommendations_snapshot)
        history = self.client.get('/farmer/agronomic-logs')
        self.assertContains(history, 'North field')
        self.assertContains(history, '91.0%')
        self.assertContains(history, f'/farmer/cv-upload/{upload.pk}/image')
        self.assertContains(history, 'Calculation Results')
        self.assertContains(history, f'{log.predicted_lkg:.2f}')
        self.assertContains(history, log.recommendations_snapshot[0]['title'])
        self.assertContains(history, log.recommendations_snapshot[0]['meta'])
        self.assertContains(history, 'history-card-date')

    def test_older_input_history_without_scan_still_renders(self):
        self.login_farmer()
        AgronomicLog.objects.create(user=self.user, variety='VMC 84-947', hectares='1',
            recommendations_summary='General: Check the field')
        history = self.client.get('/farmer/agronomic-logs')
        self.assertContains(history, 'Scan details were not recorded for this earlier calculation.')
        self.assertContains(history, 'Check the field')

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
        recent_html = response.content.decode().split('<div id="recent-scans"', 1)[1].split('<div id="scan-gallery"', 1)[0]
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

        recent_first = self.client.get('/homepage?gallery_page=2').content.decode().split('<div id="recent-scans"', 1)[1].split('<div id="scan-gallery"', 1)[0]
        self.assertEqual(recent_first.count('<div class="recent-item">'), 4)
        self.assertIn('?recent_page=2&gallery_page=2#recent-scans', recent_first)
        recent_second = self.client.get('/homepage?recent_page=2&gallery_page=2').content.decode().split('<div id="recent-scans"', 1)[1].split('<div id="scan-gallery"', 1)[0]
        self.assertEqual(recent_second.count('<div class="recent-item">'), 1)
        self.assertIn('Gallery plot 0', recent_second)
        self.assertNotIn('Gallery plot 4', recent_second)
        self.assertIn('?recent_page=1&gallery_page=2#recent-scans', recent_second)

        session = self.client.session
        session['scan_result_variety'] = 'VMC 84-524'
        session.save()
        recent_fragment = self.client.get('/homepage?recent_page=2&gallery_page=2&scan_section=recent-scans')
        self.assertContains(recent_fragment, 'id="recent-scans"')
        self.assertContains(recent_fragment, 'Gallery plot 0')
        self.assertNotContains(recent_fragment, 'id="scan-gallery"')
        self.assertNotContains(recent_fragment, 'Assessment Parameters')
        self.assertEqual(self.client.session['scan_result_variety'], 'VMC 84-524')

        gallery_fragment = self.client.get('/homepage?recent_page=2&gallery_page=2&scan_section=scan-gallery')
        self.assertContains(gallery_fragment, 'id="scan-gallery"')
        self.assertContains(gallery_fragment, 'Gallery plot 0')
        self.assertNotContains(gallery_fragment, 'id="recent-scans"')
        self.assertEqual(self.client.session['scan_result_variety'], 'VMC 84-524')

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
                response = self.client.post(route, create_payload)
                self.assertContains(response, 'authorize registration')
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

    def test_admin_and_superadmin_registration_routes_match_their_roles(self):
        self.login_admin()
        self.assertContains(self.client.get('/admin'), 'href="/admin-register"')
        admin_page = self.client.get('/admin-register')
        self.assertContains(admin_page, '<h2 style="margin: 15px 0 5px;">Admin Registration</h2>')
        self.assertNotContains(admin_page, 'name="role"')
        superadmin_page = self.client.get('/superadmin-register')
        self.assertContains(superadmin_page, '<h2 style="margin: 15px 0 5px;">Superadmin Registration</h2>')

        self.client.get('/admin-logout')
        admin = Admin.objects.create(username='regular-admin', email='regular-admin@example.invalid',
                                     role='admin', password_hash=make_password('Local-test-123!'))
        response = self.client.get('/admin-register')
        self.assertContains(response, 'Admin Registration')
        self.assertContains(response, '<form class="fade-in" method="POST" action="/admin-register">')
        self.assertContains(response, 'name="full_name"')
        self.assertContains(response, 'name="authorizer_identifier"')
        response = self.client.post('/admin-login', {'identifier': admin.username,
            'password': 'Local-test-123!', 'next': 'admin_register'})
        self.assertEqual(response['Location'], '/admin-register')
        self.assertContains(self.client.get('/admin-register'), 'Admin Registration')
        response = self.client.post('/admin-register', {'username': 'new-admin', 'full_name': 'New Admin',
            'email': 'new-admin@example.invalid', 'role': 'superadmin',
            'password': 'Local-test-123!', 'confirm_password': 'Local-test-123!'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Admin.objects.get(username='new-admin').role, 'admin')
        self.assertEqual(Admin.objects.get(username='new-admin').full_name, 'New Admin')
        response = self.client.get('/superadmin-register')
        self.assertContains(response, 'Superadmin Registration')
        self.assertContains(response, '<form class="fade-in" method="POST" action="/superadmin-register">')
        self.assertContains(response, 'name="authorizer_identifier"')
        self.client.post('/superadmin-register', {'username': 'blocked-superadmin',
            'email': 'blocked@example.invalid', 'password': 'Local-test-123!',
            'confirm_password': 'Local-test-123!',
            'authorizer_identifier': admin.username,
            'authorizer_password': 'Local-test-123!'})
        self.assertFalse(Admin.objects.filter(username='blocked-superadmin').exists())

        response = self.client.post('/superadmin-login', {'identifier': self.admin.username,
            'password': 'Local-test-123!', 'next': 'superadmin_register'})
        self.assertEqual(response['Location'], '/superadmin-register')
        response = self.client.post('/superadmin-register', {'username': 'new-superadmin',
            'full_name': 'New Superadmin',
            'email': 'new-superadmin@example.invalid', 'password': 'Local-test-123!',
            'confirm_password': 'Local-test-123!'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Admin.objects.get(username='new-superadmin').role, 'superadmin')
        self.assertEqual(Admin.objects.get(username='new-superadmin').full_name, 'New Superadmin')

    def test_registration_form_accepts_existing_account_authorization(self):
        self.assertContains(self.client.get('/admin-register'), 'name="full_name"')
        response = self.client.post('/admin-register', {
            'full_name': 'Authorized Admin', 'username': 'authorized-admin',
            'email': 'authorized-admin@example.invalid', 'password': 'Local-test-123!',
            'confirm_password': 'Local-test-123!', 'authorizer_identifier': self.admin.email,
            'authorizer_password': 'Local-test-123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Admin.objects.get(username='authorized-admin').full_name, 'Authorized Admin')
        self.client.get('/admin-logout')
        response = self.client.post('/superadmin-register', {
            'full_name': 'Authorized Superadmin', 'username': 'authorized-superadmin',
            'email': 'authorized-superadmin@example.invalid', 'password': 'Local-test-123!',
            'confirm_password': 'Local-test-123!', 'authorizer_identifier': self.admin.username,
            'authorizer_password': 'Local-test-123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Admin.objects.get(username='authorized-superadmin').role, 'superadmin')

    def test_legacy_scanner_uses_working_prediction_endpoint(self):
        self.login_farmer()
        response = self.client.get('/scan/new')
        self.assertContains(response, '/api/scan/predict?top_k=3')
        self.assertNotContains(response, '/analyze_stalk')
