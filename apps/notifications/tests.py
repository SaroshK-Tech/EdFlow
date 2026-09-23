"""Tests for the notifications module (spec §25): announcements, bell,
mark-as-read, internal inbox."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditLog
from apps.notifications.models import Announcement, Audience, InboxMessage, Notification
from apps.notifications.services import notify_announcement, notify_user, recipients_for

U = get_user_model()


class RecipientsForTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = U.objects.create_user(
            "rec-admin", "a@test.test", "pw", is_staff=True, is_active=True
        )
        cls.other = U.objects.create_user(
            "rec-other", "o@test.test", "pw", is_staff=False, is_active=True
        )
        cls.gone = U.objects.create_user(
            "rec-gone", "g@test.test", "pw", is_staff=True, is_active=False
        )

    def test_audience_all_returns_all_active(self):
        users = set(recipients_for(Audience.ALL))
        self.assertIn(self.admin.pk, users)
        self.assertIn(self.other.pk, users)
        self.assertNotIn(self.gone.pk, users)

    def test_audience_staff_filters_active_staff(self):
        users = set(recipients_for(Audience.STAFF))
        self.assertIn(self.admin.pk, users)
        self.assertNotIn(self.other.pk, users)
        self.assertNotIn(self.gone.pk, users)


class NotifyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.creator = U.objects.create_user("n-creator", "c@test.test", "pw", is_staff=True)
        cls.target = U.objects.create_user("n-target", "t@test.test", "pw", is_staff=True)

    def test_notify_announcement_skips_actor(self):
        a = Announcement.objects.create(title="Assembly", created_by=self.creator)
        created = notify_announcement(a, actor=self.creator)
        self.assertEqual(created, 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.target).count(), 1
        )
        self.assertFalse(
            Notification.objects.filter(recipient=self.creator).exists()
        )

    def test_notify_user_returns_notification(self):
        note = notify_user(self.target, "Hello", "/x", "bell")
        self.assertIsNotNone(note)
        self.assertFalse(note.is_read)


class NotificationViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = U.objects.create_superuser("admin-note", "a@test.test", "pw")
        cls.other = U.objects.create_user("note-other", "o@test.test", "pw", is_staff=True)
        cls.note = Notification.objects.create(recipient=cls.user, text="Bell ring")

    def setUp(self):
        self.client.force_login(self.user)

    def test_list_shows_own_notifications_only(self):
        Notification.objects.create(recipient=self.other, text="Not yours")
        resp = self.client.get(reverse("notifications:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Bell ring")
        self.assertNotContains(resp, "Not yours")

    def test_mark_read_redirects_to_note_url(self):
        Notification.objects.create(recipient=self.user, text="Go", url="/x")
        note = Notification.objects.get(text="Go")
        resp = self.client.get(reverse("notifications:mark_read", args=[note.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/x")
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_mark_read_without_url_goes_to_list(self):
        resp = self.client.get(reverse("notifications:mark_read", args=[self.note.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith(reverse("notifications:list")))

    def test_mark_read_ignores_other_users_note(self):
        resp = self.client.get(reverse("notifications:mark_read", args=[self.other.notifications.create(text="X").pk]))
        self.assertEqual(resp.status_code, 404)

    def test_announcement_create_notifies_and_audits(self):
        resp = self.client.post(
            reverse("notifications:announcement_add"),
            {"title": "Fire drill", "audience": Audience.ALL, "body": "Tomorrow"},
        )
        self.assertEqual(resp.status_code, 302)
        a = Announcement.objects.get(title="Fire drill")
        self.assertTrue(
            Notification.objects.filter(announcement=a, recipient=self.other).exists()
        )
        self.assertFalse(
            Notification.objects.filter(announcement=a, recipient=self.user).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(user=self.user, action="notifications").exists()
        )


class InboxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sender = U.objects.create_user("ix-sender", "s@test.test", "pw")
        cls.user = U.objects.create_superuser("ix-user", "u@test.test", "pw")

    def setUp(self):
        self.client.force_login(self.user)

    def test_compose_message(self):
        resp = self.client.post(
            reverse("notifications:compose"),
            {"recipient": self.sender.pk, "subject": "Hello", "body": "World"},
        )
        self.assertEqual(resp.status_code, 302)
        msg = InboxMessage.objects.get(subject="Hello")
        self.assertEqual(msg.sender, self.user)
        self.assertEqual(msg.recipient, self.sender)
        self.assertFalse(msg.is_read)

    def test_inbox_detail_marks_as_read(self):
        msg = InboxMessage.objects.create(
            sender=self.sender, recipient=self.user, subject="S", body="B"
        )
        resp = self.client.get(reverse("notifications:inbox_detail", args=[msg.pk]))
        self.assertEqual(resp.status_code, 200)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.read_at)