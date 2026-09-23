"""Tests for the hardware module (spec §35): device heartbeats and tickets."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.hardware.models import (
    Device,
    DeviceEvent,
    DeviceType,
    MaintenanceRequest,
    TicketStatus,
)
from apps.hardware.services import find_by_token, heartbeat

U = get_user_model()


class DeviceModelTests(TestCase):
    def test_device_str_and_status(self):
        d = Device.objects.create(name="Gate-1", device_type=DeviceType.GATEWAY)
        self.assertIn("Gate-1", str(d))
        self.assertEqual(d.status, "active")

    def test_find_by_token(self):
        d = Device.objects.create(
            name="Gate", device_type=DeviceType.GATEWAY, gateway_token="tok-123"
        )
        self.assertEqual(find_by_token("tok-123"), d)
        self.assertIsNone(find_by_token("nope"))
        self.assertIsNone(find_by_token(""))

    def test_heartbeat_creates_event(self):
        d = Device.objects.create(name="Gate", device_type=DeviceType.GATEWAY)
        ok = heartbeat(d, "error", "Sim removed")
        self.assertTrue(ok)
        self.assertTrue(DeviceEvent.objects.filter(device=d, event_type="error").exists())


class MaintenanceTicketTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = U.objects.create_superuser("admin-hw", "a@test.test", "pw")
        cls.device = Device.objects.create(name="Printer 1", device_type=DeviceType.PRINTER)

    def setUp(self):
        self.client.force_login(self.user)

    def test_ticket_number_auto_generated(self):
        t = MaintenanceRequest.objects.create(
            device=self.device, issue_title="Paper jam", priority="high"
        )
        self.assertTrue(t.ticket_number.startswith("MNT-"))
        self.assertEqual(len(MaintenanceRequest.objects.filter(device=self.device)), 1)

    def test_create_ticket_via_view(self):
        resp = self.client.post(
            reverse("hardware:maintenance_add"),
            {
                "device": self.device.pk,
                "issue_title": "Screen flickering",
                "priority": "critical",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ticket = MaintenanceRequest.objects.get(issue_title="Screen flickering")
        self.assertEqual(ticket.reported_by, self.user)
        self.assertEqual(ticket.priority, "critical")
        # Opening a ticket records a device event.
        self.assertTrue(
            DeviceEvent.objects.filter(
                device=self.device, event_type="error"
            ).exists()
        )

    def test_resolve_sets_resolved_at_and_event(self):
        ticket = MaintenanceRequest.objects.create(
            device=self.device, issue_title="Broken key", reported_by=self.user
        )
        resp = self.client.post(
            reverse("hardware:maintenance_edit", args=[ticket.pk]),
            {
                "device": self.device.pk,
                "issue_title": "Broken key",
                "priority": "medium",
                "status": TicketStatus.RESOLVED,
                "resolution_notes": "Replaced the keyboard",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)
        self.assertIsNotNone(ticket.resolved_at)
        self.assertEqual(ticket.resolution_notes, "Replaced the keyboard")
        self.assertTrue(
            DeviceEvent.objects.filter(
                device=self.device, event_type="result"
            ).exists()
        )

    def test_maintenance_list_shows_stat_counts(self):
        MaintenanceRequest.objects.create(device=self.device, issue_title="Jam")
        resp = self.client.get(reverse("hardware:maintenance"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Jam")

    def test_delete_ticket(self):
        ticket = MaintenanceRequest.objects.create(
            device=self.device, issue_title="Temp"
        )
        resp = self.client.post(reverse("hardware:maintenance_delete", args=[ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(MaintenanceRequest.objects.filter(pk=ticket.pk).exists())

    def test_device_detail_shows_tickets(self):
        ticket = MaintenanceRequest.objects.create(device=self.device, issue_title="Display")
        resp = self.client.get(reverse("hardware:device_detail", args=[self.device.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Display")