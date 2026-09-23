"""Tests for the progress module (spec §10): records, editing, PDF reports."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditLog
from apps.progress.models import ProgressRecord
from apps.students.models import Student

U = get_user_model()


class ProgressRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = U.objects.create_superuser("admin-progress", "a@test.test", "pw")
        cls.student = Student.objects.create(
            admission_number="PR-1", first_name="Progress", last_name="Kid"
        )
        cls.admin = U.objects.create_user("teacher-prog", "t@test.test", "pw")

    def setUp(self):
        self.client.force_login(self.user)

    def test_record_str(self):
        r = ProgressRecord.objects.create(
            student=self.student, score=Decimal("75.50"), category="assessment"
        )
        self.assertIn("75.50%", str(r))

    def test_create_record_via_view_writes_audit(self):
        resp = self.client.post(
            reverse("progress:add"),
            {
                "student": self.student.pk,
                "category": "homework",
                "score": "80.00",
                "remark": "Good work",
            },
        )
        rec = ProgressRecord.objects.get(student=self.student)
        self.assertEqual(rec.score, Decimal("80.00"))
        self.assertEqual(rec.category, "homework")
        self.assertEqual(rec.remark, "Good work")
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user, object_type="ProgressRecord", object_id=rec.pk
            ).exists()
        )
        self.assertEqual(resp.status_code, 302)

    def test_create_rejects_score_over_range(self):
        resp = self.client.post(
            reverse("progress:add"),
            {"student": self.student.pk, "score": "150", "category": "assessment"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ProgressRecord.objects.filter(student=self.student).exists())

    def test_edit_record(self):
        rec = ProgressRecord.objects.create(
            student=self.student, score=Decimal("50.00"), remark="Needs work"
        )
        resp = self.client.post(
            reverse("progress:record_edit", args=[rec.pk]),
            {"student": self.student.pk, "score": "66.00", "category": "skill", "remark": "Improved"},
        )
        rec.refresh_from_db()
        self.assertEqual(rec.score, Decimal("66.00"))
        self.assertEqual(rec.category, "skill")
        self.assertEqual(resp.status_code, 302)

    def test_delete_record(self):
        rec = ProgressRecord.objects.create(
            student=self.student, score=Decimal("40.00")
        )
        self.client.post(reverse("progress:record_delete", args=[rec.pk]))
        self.assertFalse(ProgressRecord.objects.filter(pk=rec.pk).exists())

    def test_records_page_lists_entries(self):
        ProgressRecord.objects.create(
            student=self.student, score=Decimal("88.00"), category="assessment"
        )
        resp = self.client.get(
            reverse("progress:records", args=[self.student.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "88.00")

    def test_pdf_report_renders(self):
        ProgressRecord.objects.create(
            student=self.student, score=Decimal("64.00"), category="assessment"
        )
        resp = self.client.get(reverse("progress:pdf", args=[self.student.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")