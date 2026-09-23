"""Tests for fees: concessions, vouchers and receipts (spec §15)."""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal

from apps.academics.models import Class
from apps.students.models import Student

from .models import (
    Concession,
    ConcessionType,
    FeeHead,
    FeePayment,
    FeeVoucher,
    FeeVoucherItem,
    StudentConcession,
    discount_for_fee_head,
    discounts_for_student,
)

U = get_user_model()


class ConcessionMathTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = Student.objects.create(admission_number="FEE-1", first_name="F")
        cls.tuition = FeeHead.objects.create(name="Tuition", amount=Decimal("1000"))
        cls.transport = FeeHead.objects.create(name="Transport", amount=Decimal("500"))
        cls.percent = Concession.objects.create(
            name="Scholar 10", concession_type=ConcessionType.SCHOLARSHIP,
            percentage=Decimal("10"),
        )
        cls.flat = Concession.objects.create(
            name="Waiver 50", concession_type=ConcessionType.CONCESSION,
            flat_amount=Decimal("50"),
        )
        cls.targeted = Concession.objects.create(
            name="Transport Only", concession_type=ConcessionType.DISCOUNT,
            percentage=Decimal("20"),
        )
        cls.targeted.fee_heads.add(cls.transport)

    def _assign(self, concession, student=None):
        return StudentConcession.objects.create(
            concession=concession, student=student or self.student
        )

    def test_percentage_discount(self):
        self.assertEqual(self.percent.discount_for(Decimal("1000")), Decimal("100"))

    def test_flat_discount(self):
        self.assertEqual(self.flat.discount_for(Decimal("1000")), Decimal("50"))

    def test_discount_capped_at_amount(self):
        big = Concession.objects.create(
            name="Huge", concession_type=ConcessionType.CONCESSION,
            flat_amount=Decimal("9999"),
        )
        self.assertEqual(big.discount_for(Decimal("100")), Decimal("100"))

    def test_discount_totals_and_caps(self):
        self.assertEqual(
            discount_for_fee_head(self.student, self.tuition, Decimal("1000")), Decimal("0")
        )
        self._assign(self.percent)
        self._assign(self.flat)
        # 10% of 1000 + 50 flat = 150, under cap.
        self.assertEqual(
            discount_for_fee_head(self.student, self.tuition, Decimal("1000")),
            Decimal("150.00"),
        )

    def test_targeted_fee_head_only(self):
        self._assign(self.targeted)
        self.assertEqual(
            discount_for_fee_head(self.student, self.transport, Decimal("500")),
            Decimal("100.00"),
        )
        self.assertEqual(
            discount_for_fee_head(self.student, self.tuition, Decimal("1000")), Decimal("0")
        )

    def test_discounts_for_student_filters_by_period(self):
        self._assign(self.percent)
        self._assign(self.flat)
        past = StudentConcession.objects.create(
            concession=self.percent, student=self.student,
            starts_on=timezone.localdate() - datetime.timedelta(days=30),
            ends_on=timezone.localdate() - datetime.timedelta(days=1),
        )
        future = StudentConcession.objects.create(
            concession=self.flat, student=self.student,
            starts_on=timezone.localdate() + datetime.timedelta(days=5),
        )
        active = discounts_for_student(self.student)
        self.assertEqual(len(active), 2)

    def test_inactive_concession_excluded(self):
        c = Concession.objects.create(
            name="Off", concession_type=ConcessionType.CONCESSION,
            percentage=Decimal("5"), is_active=False,
        )
        self.assertEqual(c.discount_for(Decimal("200")), Decimal("0"))


class StudentConcessionCurrentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = Student.objects.create(admission_number="FEE-2", first_name="G")
        cls.con = Concession.objects.create(
            name="Sch", concession_type=ConcessionType.SCHOLARSHIP, percentage=Decimal("5")
        )

    def test_is_current_true(self):
        sc = StudentConcession.objects.create(concession=self.con, student=self.student)
        self.assertTrue(sc.is_current)

    def test_is_current_false_when_inactive(self):
        sc = StudentConcession.objects.create(
            concession=self.con, student=self.student, is_active=False
        )
        self.assertFalse(sc.is_current)

    def test_is_current_false_when_future(self):
        sc = StudentConcession.objects.create(
            concession=self.con, student=self.student,
            starts_on=timezone.localdate() + datetime.timedelta(days=3),
        )
        self.assertFalse(sc.is_current)

    def test_is_current_false_when_expired(self):
        sc = StudentConcession.objects.create(
            concession=self.con, student=self.student,
            starts_on=timezone.localdate() - datetime.timedelta(days=10),
            ends_on=timezone.localdate() - datetime.timedelta(days=1),
        )
        self.assertFalse(sc.is_current)


class VoucherTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = Student.objects.create(admission_number="FEE-3", first_name="H")
        cls.head = FeeHead.objects.create(name="Admission Fee", amount=Decimal("2000"))
        cls.user = U.objects.create_superuser("fee-user", "x@x.test", "pw")

    def test_voucher_numbers_auto_generated(self):
        v = FeeVoucher.objects.create(student=self.student, created_by=self.user)
        self.assertTrue(v.voucher_number.startswith("VCH-"))
        FeeVoucherItem.objects.create(
            voucher=v, fee_head=self.head, amount=Decimal("2000"), discount=Decimal("100")
        )
        self.assertEqual(v.subtotal, 2000)
        self.assertEqual(v.total_discount, 100)
        self.assertEqual(v.total, 1900)
        item = v.items.get()
        self.assertEqual(item.net, Decimal("1900"))

    def test_receipt_numbers_auto_generated(self):
        p = FeePayment.objects.create(
            student=self.student, fee_head=self.head, amount=Decimal("500")
        )
        self.assertTrue(p.receipt_number.startswith("RCPT-"))