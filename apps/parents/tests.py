"""Tests for the parents module (spec §6): profile, detail view, comms, audit."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.communication.models import Outbox
from apps.core.models import AuditLog
from apps.fees.models import FeeHead, FeePayment, FeeVoucher, FeeVoucherItem
from apps.parents.models import Parent
from apps.students.models import Student

U = get_user_model()


class ParentModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = Parent.objects.create(
            first_name="Jane", last_name="Wanjiru", phone="0711000000"
        )

    def test_full_name_and_str(self):
        self.assertEqual(self.parent.full_name, "Jane Wanjiru")
        self.assertEqual(str(self.parent), "Jane Wanjiru")

    def test_new_fields_default_to_empty(self):
        self.assertEqual(self.parent.emergency_contact, "")
        self.assertEqual(self.parent.notes, "")
        self.assertIsNone(self.parent.user)

    def test_user_link(self):
        user = U.objects.create_user("parent-user", "p@test.test", "pw")
        self.parent.user = user
        self.parent.save(update_fields=["user"])
        self.assertEqual(self.parent.user, user)
        self.assertEqual(user.parent_profile, self.parent)


class ParentDetailViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = U.objects.create_superuser("admin-parent", "a@test.test", "pw")
        cls.parent = Parent.objects.create(
            first_name="Mama", last_name="Njeri", phone="0722000000",
            emergency_contact="0722999999",
        )
        cls.student = Student.objects.create(
            admission_number="P-DET-1", first_name="Kevin"
        )
        cls.parent.students.add(cls.student)

    def setUp(self):
        self.client.force_login(self.user)

    def test_detail_page_lists_children(self):
        resp = self.client.get(reverse("parents:detail", args=[self.parent.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Kevin")
        self.assertContains(resp, self.parent.full_name)

    def test_detail_sums_child_fee_balance(self):
        fee = FeeHead.objects.create(name="Tuition", amount=Decimal("1000"))
        voucher = FeeVoucher.objects.create(student=self.student)
        FeeVoucherItem.objects.create(
            voucher=voucher, fee_head=fee, amount=Decimal("1000")
        )
        FeePayment.objects.create(
            student=self.student, fee_head=fee, amount=Decimal("200")
        )
        resp = self.client.get(reverse("parents:detail", args=[self.parent.pk]))
        self.assertContains(resp, "800.00")

    def test_detail_shows_communication_with_child(self):
        Outbox.objects.create(
            student=self.student,
            recipient="Mama Njeri",
            phone=self.parent.phone,
            message="Fee reminder",
            status="pending",
        )
        resp = self.client.get(reverse("parents:detail", args=[self.parent.pk]))
        self.assertContains(resp, "Fee reminder")

    def test_detail_renders_with_no_children(self):
        lone = Parent.objects.create(first_name="Alone", last_name="Walks")
        resp = self.client.get(reverse("parents:detail", args=[lone.pk]))
        self.assertEqual(resp.status_code, 200)


class ParentAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = U.objects.create_superuser("admin-audit", "x@x.test", "pw")

    def setUp(self):
        self.client.force_login(self.user)

    def test_creating_parent_writes_audit(self):
        self.client.post(
            reverse("parents:add"),
            {"first_name": "Audit", "last_name": "Man", "phone": "0733000000"},
        )
        parent = Parent.objects.get(first_name="Audit")
        self.assertEqual(parent.last_name, "Man")
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.user, object_type="Parent", object_id=parent.pk
            ).exists()
        )