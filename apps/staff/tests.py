"""Tests for the staff module (spec §16): profiles, documents, ID cards."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditLog
from apps.staff.models import Staff, StaffDocument

U = get_user_model()


class StaffModelTests(TestCase):
    def test_full_name_joins_parts(self):
        s = Staff.objects.create(
            employee_code="S-1", first_name="Grace", middle_name="A", last_name="Wekesa"
        )
        self.assertEqual(s.full_name, "Grace A Wekesa")
        self.assertIn("S-1", str(s))

    def test_years_of_service_based_on_joining_date(self):
        s = Staff.objects.create(
            employee_code="S-2", first_name="Ben",
            joining_date=date(2022, 9, 1), status="active",
        )
        self.assertGreater(s.years_of_service, 3.5)

    def test_no_joining_date_means_no_service(self):
        s = Staff.objects.create(employee_code="S-3", first_name="Ada", status="active")
        self.assertIsNone(s.years_of_service)

    def test_document_str(self):
        s = Staff.objects.create(employee_code="S-4", first_name="Doc")
        d = StaffDocument.objects.create(
            staff=s, title="Degree cert", document_type="qualification"
        )
        self.assertIn("Degree cert", str(d))
        self.assertEqual(d.document_type, "qualification")


class StaffViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = U.objects.create_superuser("admin-staff", "a@test.test", "pw")
        cls.member = Staff.objects.create(
            employee_code="S-V-1", first_name="Victor", last_name="Otieno",
            is_teacher=True, designation="Maths Teacher", status="active",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_detail_page_shows_member(self):
        resp = self.client.get(reverse("staff:detail", args=[self.member.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Victor Otieno")

    def test_id_card_page_renders(self):
        resp = self.client.get(reverse("staff:id_card", args=[self.member.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "S-V-1")

    def test_upload_document(self):
        f = SimpleUploadedFile("cert.pdf", b"PDFDATA", content_type="application/pdf")
        resp = self.client.post(
            reverse("staff:document_add", args=[self.member.pk]),
            {"title": "CV", "document_type": "other", "file": f},
        )
        doc = StaffDocument.objects.get(title="CV")
        self.assertEqual(doc.staff, self.member)
        self.assertEqual(doc.uploaded_by, self.user)
        self.assertEqual(resp.status_code, 302)

    def test_upload_writes_audit(self):
        f = SimpleUploadedFile("id.pdf", b"IDDATA", content_type="application/pdf")
        self.client.post(
            reverse("staff:document_add", args=[self.member.pk]),
            {"title": "National ID", "document_type": "id_proof", "file": f},
        )
        doc = StaffDocument.objects.get(title="National ID")
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user, object_type="StaffDocument", object_id=doc.pk
            ).exists()
        )

    def test_document_shown_on_detail(self):
        StaffDocument.objects.create(
            staff=self.member, title="Appointment letter", document_type="appointment"
        )
        resp = self.client.get(reverse("staff:detail", args=[self.member.pk]))
        self.assertContains(resp, "Appointment letter")