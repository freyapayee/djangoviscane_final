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
        self.assertContains(response, 'id="farmer-feedback-message"')

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
