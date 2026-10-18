from django.test import TestCase, Client
from .models import User, Notification, AgronomicLog


class FarmerNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(fullname='Farmer', email='menu@example.test', phone='123', password='unused')
        session = self.client.session
        session['user_id'] = self.user.pk
        session.save()

    def test_dashboard_moves_communications_outside_main(self):
        response = self.client.get('/homepage')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        main = html.split('<main', 1)[1].split('</main>', 1)[0]
        self.assertNotIn('Farmer Pages', html)
        self.assertNotIn('News &amp; Announcements', main)
        self.assertNotIn('feedback_message', main)
        self.assertContains(response, 'id="farmer-menu"')
        self.assertNotContains(response, 'id="farmer-feedback-message"')
        self.assertContains(response, 'href="/farmer/news"')
        for href in ['/scan/new', '/homepage#scan-gallery', '/homepage#recent-scans', '/homepage#calc-form', '/farmer/recommendations', '/farmer/agronomic-logs', '/farmer/settings']:
            self.assertContains(response, f'href="{href}"')
        self.assertLess(html.index('header-date-weather'), html.index('id="farmer-menu-toggle"'))
        self.assertLess(html.index('data-start-farmer-tour'), html.index('id="farmer-menu-toggle"'))
        self.assertLess(html.index('farmer-settings-link'), html.index('id="farmer-menu-toggle"'))
        header = html.split('<header class="dashboard-header">', 1)[1].split('</header>', 1)[0]
        self.assertNotIn('href="/homepage"', header)

    def test_news_page_and_feedback_redirect(self):
        Notification.objects.create(title='New announcement', message='News message')
        response = self.client.get('/farmer/news', HTTP_USER_AGENT='ViscaneFarmer/1.0')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'News message')
        self.assertContains(response, 'id="farmer-feedback-message"')
        self.assertContains(response, 'data-tour-target="farmer-news"')
        response = self.client.post('/farmer/feedback', {'feedback_message': 'My suggestion', 'return_to': 'news'})
        self.assertTrue(response.url.startswith('/farmer/news?message='))
        response = self.client.post('/farmer/feedback', {'feedback_message': '', 'return_to': 'news'})
        self.assertTrue(response.url.startswith('/farmer/news?error='))
        self.assertEqual(Client().get('/farmer/news').status_code, 302)

    def test_unread_persistence_new_items_and_user_isolation(self):
        item = Notification.objects.create(title='Update', message='Announcement')
        log = AgronomicLog.objects.create(user=self.user, recommendations_snapshot=[{'title': 'Suggestion'}])
        other = User.objects.create(fullname='Other', email='other@example.test', phone='456', password='unused')
        AgronomicLog.objects.create(user=other, recommendations_snapshot=[{'title': 'Private'}])
        data = self.client.get('/farmer/notifications').json()
        self.assertEqual(data['unread_announcements'], 1)
        self.assertEqual(data['unread_suggestions'], 1)
        self.assertEqual(data['suggestion_id'], log.pk)
        response = self.client.post('/farmer/notifications', {'announcement_id': item.pk, 'suggestion_id': log.pk})
        self.assertEqual(response.json()['unread_suggestions'], 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.seen_announcement_id, item.pk)
        Notification.objects.create(title='New', message='New announcement')
        self.assertEqual(self.client.get('/farmer/notifications').json()['unread_announcements'], 1)
        self.client.post('/farmer/notifications', {'announcement_id': 0, 'suggestion_id': 0})
        self.user.refresh_from_db()
        self.assertEqual(self.user.seen_announcement_id, item.pk)
        other.refresh_from_db()
        self.assertEqual(other.seen_announcement_id, 0)

    def test_mobile_farmer_can_fetch_notifications(self):
        response = self.client.get("/farmer/notifications", HTTP_USER_AGENT="ViscaneFarmer/1.0")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_authentication_csrf_and_invalid_ids(self):
        self.assertEqual(Client().get('/farmer/notifications').status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        session = strict.session
        session['user_id'] = self.user.pk
        session.save()
        self.assertEqual(strict.post('/farmer/notifications').status_code, 403)
        self.assertEqual(self.client.post('/farmer/notifications', {'announcement_id': 'bad'}).status_code, 400)
