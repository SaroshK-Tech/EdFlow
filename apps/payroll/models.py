import calendar

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class ComponentKind(models.TextChoices):
    ALLOWANCE = "allowance", "Allowance"
    DEDUCTION = "deduction", "Deduction"


class AppliesTo(models.TextChoices):
    ALL = "all", "All staff"
    TEACHER = "teacher", "Teachers only"
    NON_TEACHING = "non_teaching", "Non-teaching only"


class SalaryComponent(models.Model):
    """An allowance or deduction: fixed amount or percentage of basic."""

    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(
        max_length=10, choices=ComponentKind.choices, default=ComponentKind.ALLOWANCE
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    applies_to = models.CharField(
        max_length=20, choices=AppliesTo.choices, default=AppliesTo.ALL
    )
    is_taxable = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name


class PayrollStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PROCESSED = "processed", "Processed"
    PAID = "paid", "Paid"


class PayrollRun(models.Model):
    """One monthly payroll run; unique per (month, year)."""

    title = models.CharField(max_length=100, blank=True)
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10, choices=PayrollStatus.choices, default=PayrollStatus.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="payroll_runs",
    )
    created_at = models.DateTimeField(default=timezone.now)
    paid_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["month", "year"], name="unique_payroll_month_year"),
        ]

    @property
    def period_label(self):
        return f"{calendar.month_name[self.month]} {self.year}"

    def save(self, *args, **kwargs):
        if not self.title:
            self.title = self.period_label
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.period_label})"


class PaySlip(models.Model):
    """Computed pay slip for one staff member within a run."""

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="slips")
    staff = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="payslips"
    )
    basic = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["staff__first_name", "staff__employee_code"]
        constraints = [
            models.UniqueConstraint(fields=["run", "staff"], name="unique_payslip_run_staff"),
        ]

    @property
    def allowances(self):
        return self.data.get("allowances", [])

    @property
    def deductions(self):
        return self.data.get("deductions", [])

    def __str__(self):
        return f"{self.run} — {self.staff}"