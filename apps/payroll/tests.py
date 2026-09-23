"""Tests for the payroll module (spec §16): components, processing, per-staff slips."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.payroll.models import (
    AppliesTo,
    ComponentKind,
    PaySlip,
    PayrollRun,
    PayrollStatus,
    SalaryComponent,
)
from apps.payroll.services import applies_to_staff, component_value, process_run
from apps.staff.models import Staff
from apps.students.models import Status

U = get_user_model()


class ComponentValueTests(TestCase):
    def test_fixed_amount_wins(self):
        c = SalaryComponent.objects.create(
            name="Fixed", kind=ComponentKind.ALLOWANCE, amount="2500", percentage="10.00"
        )
        self.assertEqual(component_value(c, Decimal("50000")), Decimal("2500"))

    def test_percentage_of_basic(self):
        c = SalaryComponent.objects.create(
            name="Per", kind=ComponentKind.ALLOWANCE, percentage="12.50"
        )
        self.assertEqual(component_value(c, Decimal("40000")), Decimal("5000"))

    def test_no_value(self):
        c = SalaryComponent.objects.create(name="Zero", kind=ComponentKind.ALLOWANCE)
        self.assertEqual(component_value(c, Decimal("40000")), Decimal("0"))


class AppliesToTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = Staff.objects.create(
            employee_code="PL-1", first_name="T", is_teacher=True, status=Status.ACTIVE
        )
        cls.admin = Staff.objects.create(
            employee_code="PL-2", first_name="A", is_teacher=False, status=Status.ACTIVE
        )

    def test_all_staff(self):
        c = SalaryComponent.objects.create(
            name="C", applies_to=AppliesTo.ALL, kind=ComponentKind.ALLOWANCE
        )
        self.assertTrue(applies_to_staff(c, self.teacher))
        self.assertTrue(applies_to_staff(c, self.admin))

    def test_teacher_only(self):
        c = SalaryComponent.objects.create(
            name="C", applies_to=AppliesTo.TEACHER, kind=ComponentKind.ALLOWANCE
        )
        self.assertTrue(applies_to_staff(c, self.teacher))
        self.assertFalse(applies_to_staff(c, self.admin))

    def test_non_teaching_only(self):
        c = SalaryComponent.objects.create(
            name="C", applies_to=AppliesTo.NON_TEACHING, kind=ComponentKind.ALLOWANCE
        )
        self.assertFalse(applies_to_staff(c, self.teacher))
        self.assertTrue(applies_to_staff(c, self.admin))


class ProcessRunTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = Staff.objects.create(
            employee_code="PL-10", first_name="Pay", last_name="Slip",
            is_teacher=True, salary=Decimal("50000"), status=Status.ACTIVE,
        )
        cls.admin = Staff.objects.create(
            employee_code="PL-11", first_name="Office", is_teacher=False,
            salary=Decimal("30000"), status=Status.ACTIVE,
        )
        cls.payroll_run = PayrollRun.objects.create(month=6, year=2026)
        SalaryComponent.objects.create(
            name="House allowance", kind=ComponentKind.ALLOWANCE, amount="10000",
            applies_to=AppliesTo.ALL,
        )
        SalaryComponent.objects.create(
            name="TSC %", kind=ComponentKind.DEDUCTION, percentage="1.50",
            applies_to=AppliesTo.TEACHER,
        )

    def test_process_run_computes_slips(self):
        count = process_run(self.payroll_run)
        self.assertEqual(count, 2)
        self.assertEqual(self.payroll_run.status, PayrollStatus.PROCESSED)

        slip = PaySlip.objects.get(run=self.payroll_run, staff=self.teacher)
        self.assertEqual(slip.allowances_total, Decimal("10000.00"))
        # 50000 * 1.5% = 750
        self.assertEqual(slip.deductions_total, Decimal("750.00"))
        self.assertEqual(slip.net, Decimal("59250.00"))

        admin_slip = PaySlip.objects.get(run=self.payroll_run, staff=self.admin)
        self.assertEqual(admin_slip.deductions_total, Decimal("0.00"))
        self.assertEqual(admin_slip.net, Decimal("40000.00"))

    def test_reprocess_is_idempotent(self):
        process_run(self.payroll_run)
        process_run(self.payroll_run)
        self.assertEqual(PaySlip.objects.filter(run=self.payroll_run).count(), 2)


class PayrollViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = U.objects.create_superuser("admin-payroll", "a@test.test", "pw")
        cls.staff = Staff.objects.create(
            employee_code="PL-20", first_name="View", last_name="Slip",
            is_teacher=True, status=Status.ACTIVE,
        )
        cls.payroll_run = PayrollRun.objects.create(month=5, year=2026)
        SalaryComponent.objects.create(name="Transport", kind=ComponentKind.ALLOWANCE, amount="2000")

    def setUp(self):
        self.client.force_login(self.user)

    def test_components_page(self):
        resp = self.client.get(reverse("payroll:components"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Transport")

    def test_add_component(self):
        resp = self.client.post(
            reverse("payroll:component_add"),
            {
                "name": "Medical",
                "kind": ComponentKind.DEDUCTION,
                "amount": "1500",
                "applies_to": AppliesTo.ALL,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SalaryComponent.objects.filter(name="Medical").exists())

    def test_component_requires_value(self):
        resp = self.client.post(
            reverse("payroll:component_add"),
            {"name": "Empty", "kind": ComponentKind.ALLOWANCE, "applies_to": AppliesTo.ALL},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SalaryComponent.objects.filter(name="Empty").exists())

    def test_staff_slips_page(self):
        process_run(self.payroll_run)
        resp = self.client.get(reverse("payroll:staff_slips", args=[self.staff.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Transport")