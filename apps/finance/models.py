from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.fees.models import PaymentMethod


class ExpenseCategory(models.Model):
    """Category for school expenditure (spec §15 'Expenses')."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Expense Categories"

    def __str__(self):
        return self.name


class Expense(models.Model):
    """An outgoing payment / expense entry (spec §15)."""

    category = models.ForeignKey(
        ExpenseCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses",
    )
    title = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(default=timezone.localdate)
    method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    payee = models.CharField(max_length=150, blank=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    notes = models.CharField(max_length=250, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="expenses_recorded",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def __str__(self):
        return f"{self.title} ({self.amount}) on {self.expense_date}"


class Refund(models.Model):
    """Money returned to a parent/student (spec §15 'Refunds')."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="refunds"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refund_date = models.DateField(default=timezone.localdate)
    method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    reason = models.CharField(max_length=250)
    reference = models.CharField(
        max_length=50, blank=True,
        help_text="Optional reference, e.g. the original fee receipt number.",
    )
    notes = models.CharField(max_length=250, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="refunds_recorded",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-refund_date", "-id"]

    def __str__(self):
        return f"Refund {self.amount} to {self.student} ({self.refund_date})"