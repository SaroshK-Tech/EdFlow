import datetime

from django.db import models
from django.utils import timezone
from decimal import Decimal


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    BANK = "bank", "Bank"
    CHEQUE = "cheque", "Cheque"
    CARD = "card", "Card"
    ONLINE = "online", "Online"  # optional add-on, never required offline


class FeeHead(models.Model):
    """A chargeable fee item: tuition, transport, admission, etc. (spec §15)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_recurring = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Fee Heads"

    def __str__(self):
        return self.name


class FeePayment(models.Model):
    """A recorded fee payment/receipt."""

    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="payments"
    )
    fee_head = models.ForeignKey(
        "fees.FeeHead", on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    paid_on = models.DateField(default=datetime.date.today)
    received_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="payments_collected",
    )
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-paid_on"]

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            super().save(*args, **kwargs)
            self.receipt_number = f"RCPT-{self.paid_on:%Y%m%d}-{self.pk:06d}"
            # Use update to avoid re-entering full save logic needlessly.
            self._state.fields_cache = {}
            FeePayment.objects.filter(pk=self.pk).update(receipt_number=self.receipt_number)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} — {self.amount} ({self.student})"


class VoucherStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    CANCELLED = "cancelled", "Cancelled"


class FeeVoucher(models.Model):
    """A fee demand voucher for one student (spec §15 'student invoices').

    Vouchers are generated in bulk per class/section and carry the fee
    breakdown plus the school's banking details for payment.
    """

    voucher_number = models.CharField(max_length=50, unique=True, blank=True)
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="vouchers"
    )
    issued_on = models.DateField(default=datetime.date.today)
    due_date = models.DateField(default=datetime.date.today)
    status = models.CharField(
        max_length=10, choices=VoucherStatus.choices, default=VoucherStatus.ISSUED
    )
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="vouchers_created",
    )

    class Meta:
        ordering = ["-issued_on", "-created_at"]

    def __str__(self):
        return f"{self.voucher_number} — {self.student}"

    @property
    def subtotal(self):
        return self.items.aggregate(total=models.Sum("amount"))["total"] or 0

    @property
    def total_discount(self):
        return self.items.aggregate(total=models.Sum("discount"))["total"] or 0

    @property
    def total(self):
        return self.subtotal - self.total_discount

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            super().save(*args, **kwargs)
            self.voucher_number = f"VCH-{self.issued_on:%Y%m%d}-{self.pk:06d}"
            # Update to avoid re-entering the full save loop needlessly.
            self._state.fields_cache = {}
            FeeVoucher.objects.filter(pk=self.pk).update(
                voucher_number=self.voucher_number
            )
        else:
            super().save(*args, **kwargs)


class FeeVoucherItem(models.Model):
    """A single fee line on a voucher (fee head + amount + discount)."""

    voucher = models.ForeignKey(
        FeeVoucher, on_delete=models.CASCADE, related_name="items"
    )
    fee_head = models.ForeignKey(
        "fees.FeeHead", on_delete=models.PROTECT, related_name="voucher_items"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ("voucher", "fee_head")

    @property
    def net(self):
        return self.amount - self.discount

    def __str__(self):
        return f"{self.voucher} — {self.fee_head.name} ({self.net})"


class ConcessionType(models.TextChoices):
    SCHOLARSHIP = "scholarship", "Scholarship"
    CONCESSION = "concession", "Concession"
    DISCOUNT = "discount", "Discount"


class ConcessionBase(models.Model):
    """A discount scheme: scholarship, concession or discount (spec §15).

    It is degree-agnostic: a concession may apply to a percentage or fixed
    amount and may target specific fee heads or all of them.
    """

    name = models.CharField(max_length=100)
    concession_type = models.CharField(
        max_length=20, choices=ConcessionType.choices, default=ConcessionType.CONCESSION
    )
    description = models.TextField(blank=True)

    # None/0 => discount applies to all fee heads on the voucher.
    fee_heads = models.ManyToManyField(
        "fees.FeeHead", related_name="concessions", blank=True
    )

    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Percentage off the (net) amount, e.g. 25.00 for 25%.",
    )
    flat_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Fixed amount off per applicable fee head.",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def scheme_label(self):
        return dict(ConcessionType.choices).get(self.concession_type, self.concession_type)

    def discount_for(self, amount):
        """Return the discount (0..amount) applied to `amount`."""
        if not self.is_active:
            return Decimal("0")
        if self.percentage is not None and self.percentage:
            value = (amount or Decimal("0")) * self.percentage / Decimal("100")
        elif self.flat_amount is not None:
            value = self.flat_amount
        else:
            value = Decimal("0")
        if value < 0:
            value = Decimal("0")
        if value > (amount or Decimal("0")):
            value = amount or Decimal("0")
        return value


class Concession(ConcessionBase):
    class Meta(ConcessionBase.Meta):
        verbose_name = "Scholarship / Concession"
        verbose_name_plural = "Scholarships & Concessions"


class StudentConcession(models.Model):
    """Assignment of a concession scheme to one student, for a period."""

    concession = models.ForeignKey(
        Concession, on_delete=models.CASCADE, related_name="assignments"
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="concessions"
    )
    starts_on = models.DateField(default=datetime.date.today)
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="concessions_created",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["concession", "student", "starts_on"],
                name="unique_student_concession_period",
            )
        ]

    def __str__(self):
        return f"{self.student} — {self.concession.name}"

    @property
    def is_current(self):
        today = timezone.localdate()
        if not self.is_active:
            return False
        if self.ends_on and self.ends_on < today:
            return False
        return self.starts_on <= today


def discounts_for_student(student):
    """Return active (Concession, percent_applied) pairs for `student`."""
    out = []
    today = timezone.localdate()
    for assignment in student.concessions.select_related("concession").filter(is_active=True):
        concession = assignment.concession
        if not concession.is_active:
            continue
        if assignment.ends_on and assignment.ends_on < today:
            continue
        if assignment.starts_on > today:
            continue
        out.append(concession)
    return out


def discount_for_fee_head(student, fee_head, amount):
    """Sum of all active concessions affecting `fee_head` on `amount`."""
    total = Decimal("0")
    for concession in discounts_for_student(student):
        if concession.fee_heads.exists() and not concession.fee_heads.filter(pk=fee_head.pk).exists():
            continue
        total += concession.discount_for(amount)
    if total > amount:
        total = amount
    return total.quantize(Decimal("0.01"))