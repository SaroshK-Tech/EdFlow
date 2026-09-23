"""Tests for communication services & models (spec §12)."""

import datetime

from django.test import TestCase
from django.utils import timezone

from apps.academics.models import Class
from apps.parents.models import Parent
from apps.school.models import SchoolProfile
from apps.students.models import Student

from .models import MessageBatch, MessageTemplate, Outbox, OutboxStatus
from .services import (
    autosend,
    claim_due,
    enqueue_messages,
    render_body,
    report_results,
    resolve_recipients,
    retry_message,
    student_context,
)


class RenderBodyTests(TestCase):
    def test_substitutes_known_placeholders(self):
        out = render_body("Hello {name}, your fee is {amount}.", name="Asha", amount=500)
        self.assertEqual(out, "Hello Asha, your fee is 500.")

    def test_leaves_unknown_placeholders_untouched(self):
        out = render_body("Hi {missing}")
        self.assertEqual(out, "Hi {missing}")

    def test_empty_value_placeholder_preserved(self):
        out = render_body("Hi {name}!", name=None)
        self.assertEqual(out, "Hi {name}!")


class StudentContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.klass = Class.objects.create(name="SMS-A")
        cls.student = Student.objects.create(
            admission_number="SMS-1", first_name="A", last_name="B", klass=cls.klass,
            phone="0712345678",
        )
        cls.parent = Parent.objects.create(
            first_name="Guardian", last_name="One", phone="0799887766", is_primary=True
        )
        cls.parent.students.add(cls.student)

    def test_includes_student_and_parent_fields(self):
        ctx = student_context(self.student)
        self.assertEqual(ctx["student_name"], "A B")
        self.assertEqual(ctx["admission_number"], "SMS-1")
        self.assertEqual(ctx["class_name"], "SMS-A")
        self.assertEqual(ctx["parent_name"], "Guardian One")

    def test_guardian_without_phone_is_blank(self):
        self.parent.phone = ""
        self.parent.save()
        ctx = student_context(self.student)
        self.assertEqual(ctx["parent_name"], "Guardian One")


class QueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.klass = Class.objects.create(name="SMS-B")
        cls.student = Student.objects.create(
            admission_number="SMS-2", first_name="C", last_name="D", klass=cls.klass,
            phone="+254712121212",
        )
        cls.template = MessageTemplate.objects.create(
            key="test_greeting", name="Greeting", body="Hello {student_name}"
        )

    def test_enqueue_messages_skips_missing_numbers(self):
        recipients = [
            {"name": "Ok", "phone": "0711000000", "student": None, "context": {}},
            {"name": "Bad", "phone": "", "student": None, "context": {}},
        ]
        n = enqueue_messages(recipients, "Hi there")
        self.assertEqual(n, 1)
        self.assertEqual(Outbox.objects.count(), 1)

    def test_enqueue_messages_with_template_and_student(self):
        rec = {
            "name": "Parent",
            "phone": "0722000000",
            "student": self.student,
            "context": student_context(self.student),
        }
        n = enqueue_messages([rec], self.template.body, template=self.template)
        self.assertEqual(n, 1)
        msg = Outbox.objects.get()
        self.assertEqual(msg.template_key, "test_greeting")
        self.assertEqual(msg.recipient, "0722000000")
        self.assertEqual(msg.status, OutboxStatus.PENDING)

    def test_claim_due_marks_processing_and_increments_attempts(self):
        rec = {"phone": "0722000000", "student": None, "context": {}}
        enqueue_messages([rec], "body")
        msg = Outbox.objects.get()
        due = claim_due(limit=10)
        self.assertEqual(len(due), 1)
        msg.refresh_from_db()
        self.assertEqual(msg.status, OutboxStatus.PROCESSING)
        self.assertEqual(msg.attempt_count, 1)

    def test_retry_cancelled_is_refused(self):
        msg = Outbox.objects.create(
            recipient="0711000000", message="x", status=OutboxStatus.CANCELLED
        )
        self.assertFalse(retry_message(msg))
        msg.refresh_from_db()
        self.assertEqual(msg.status, OutboxStatus.CANCELLED)

    def test_retry_pending(self):
        msg = Outbox.objects.create(
            recipient="0711000000", message="x", status=OutboxStatus.FAILED,
            failure_reason="boom",
        )
        self.assertTrue(retry_message(msg))
        msg.refresh_from_db()
        self.assertEqual(msg.status, OutboxStatus.PENDING)
        self.assertEqual(msg.failure_reason, "")

    def test_report_results_counts(self):
        recipients = [
            {"phone": "0711", "student": None, "context": {}},
            {"phone": "0722", "student": None, "context": {}},
            {"phone": "0733", "student": None, "context": {}},
        ]
        enqueue_messages(recipients, "x")
        ids = list(Outbox.objects.values_list("pk", flat=True))
        updated = report_results(
            [
                {"id": ids[0], "status": OutboxStatus.SENT, "gateway": "gw1"},
                {"id": ids[1], "status": OutboxStatus.FAILED, "error": "no network"},
                {"id": 99999, "status": OutboxStatus.SENT},
            ]
        )
        self.assertEqual(updated["sent"], 1)
        self.assertEqual(updated["failed"], 1)
        self.assertEqual(updated["unknown"], 1)
        self.assertEqual(Outbox.objects.filter(status=OutboxStatus.SENT).count(), 1)
        self.assertEqual(Outbox.objects.filter(gateway="gw1").count(), 1)

    def test_autosend_sends_due(self):
        recipients = [
            {"phone": "0711", "student": None, "context": {}},
            {"phone": "0722", "student": None, "context": {}},
        ]
        enqueue_messages(recipients, "x")
        claimed, sent = autosend(limit=10)
        self.assertEqual(claimed, 2)
        self.assertEqual(sent, 2)
        self.assertEqual(Outbox.objects.filter(status=OutboxStatus.SENT).count(), 2)


class ResolveRecipientsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.klass = Class.objects.create(name="SMS-C")
        cls.student = Student.objects.create(
            admission_number="SMS-3", first_name="E", last_name="F", klass=cls.klass,
            phone="0712333444",
        )
        cls.parent = Parent.objects.create(first_name="Pri", phone="0799000111", is_primary=True)
        cls.parent.students.add(cls.student)

    def test_manual_mode(self):
        recs = resolve_recipients("manual", manual_text="Asha,0711000000\n0722000000\n\n")
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["name"], "Asha")
        self.assertEqual(recs[0]["phone"], "0711000000")

    def test_class_mode_includes_student_and_parent(self):
        recs = resolve_recipients("class", klass=self.klass)
        phones = {r["phone"] for r in recs}
        self.assertIn("0712333444", phones)
        self.assertIn("0799000111", phones)

    def test_excludes_left_students(self):
        self.student.status = "left"
        self.student.save()
        recs = resolve_recipients("all_students")
        self.assertEqual(recs, [])