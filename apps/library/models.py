import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Author(models.Model):
    """Book author (spec §20)."""

    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    """Library category such as Fiction, Science (spec §20)."""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Publisher(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(models.Model):
    """A bibliographic title held by the library (spec §20)."""

    title = models.CharField(max_length=300)
    author = models.ForeignKey(
        Author, on_delete=models.PROTECT, related_name="books"
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="books",
    )
    publisher = models.ForeignKey(
        Publisher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="books",
    )
    isbn = models.CharField(max_length=30, unique=True, blank=True)
    language = models.CharField(max_length=50, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    shelf = models.CharField(max_length=50, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def available_copies(self):
        return self.copies.filter(status=CopyStatus.AVAILABLE).count()

    @property
    def total_copies(self):
        return self.copies.count()


class CopyStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    ISSUED = "issued", "Issued"
    LOST = "lost", "Lost"
    DAMAGED = "damaged", "Damaged"
    WITHDRAWN = "withdrawn", "Withdrawn"


class CopyCondition(models.TextChoices):
    NEW = "new", "New"
    GOOD = "good", "Good"
    WORN = "worn", "Worn"


class BookCopy(models.Model):
    """A single physical copy of a book, tracked by barcode (spec §20)."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    barcode = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(
        max_length=12, choices=CopyStatus.choices, default=CopyStatus.AVAILABLE
    )
    condition = models.CharField(
        max_length=8, choices=CopyCondition.choices, default=CopyCondition.GOOD
    )
    acquired_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["barcode"]

    def __str__(self):
        return f"{self.barcode} — {self.book.title}"

    def save(self, *args, **kwargs):
        if not self.barcode:
            super().save(*args, **kwargs)
            self.barcode = f"BK{self.pk:06d}"
            self._state.fields_cache = {}
            BookCopy.objects.filter(pk=self.pk).update(barcode=self.barcode)
        else:
            super().save(*args, **kwargs)


class MemberStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    BLOCKED = "blocked", "Blocked"


class Member(models.Model):
    """A library borrower, linked to a student or a staff member (spec §20)."""

    student = models.OneToOneField(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="library_membership",
    )
    staff = models.OneToOneField(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="library_membership",
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    joined_on = models.DateField(default=datetime.date.today)
    status = models.CharField(
        max_length=10, choices=MemberStatus.choices, default=MemberStatus.ACTIVE
    )

    class Meta:
        ordering = ["name"]

    def clean(self):
        if not self.student_id and not self.staff_id:
            raise ValidationError(
                "A library member must be linked to a student or a staff member."
            )

    def save(self, *args, **kwargs):
        if self.student_id:
            self.name = self.student.full_name or self.student.admission_number
        elif self.staff_id:
            self.name = self.staff.full_name or self.staff.employee_code
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class LibrarySettings(models.Model):
    """Singleton settings for the library module (spec §20)."""

    fine_per_day = models.DecimalField(max_digits=6, decimal_places=2, default=5)
    loan_duration_days = models.PositiveIntegerField(default=14)
    lost_book_fine = models.DecimalField(max_digits=8, decimal_places=2, default=200)

    class Meta:
        verbose_name_plural = "Library Settings"

    def __str__(self):
        return "Library settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def default_due_date():
    days = LibrarySettings.get_solo().loan_duration_days
    return datetime.date.today() + datetime.timedelta(days=days)


class Issue(models.Model):
    """A book copy lent to a member (spec §20)."""

    copy = models.ForeignKey(BookCopy, on_delete=models.PROTECT, related_name="issues")
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="issues")
    issued_on = models.DateField(default=datetime.date.today)
    due_date = models.DateField(default=default_due_date)
    returned_on = models.DateField(null=True, blank=True)
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    fine_paid = models.BooleanField(default=False)
    remark = models.TextField(blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="library_issues",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-issued_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["copy"],
                condition=models.Q(returned_on__isnull=True),
                name="library_unique_open_issue_per_copy",
            )
        ]

    def __str__(self):
        return f"{self.copy.barcode} → {self.member.name}"

    @property
    def is_overdue(self):
        return self.returned_on is None and self.due_date < datetime.date.today()

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        return (datetime.date.today() - self.due_date).days

    @property
    def computed_fine(self):
        rate = LibrarySettings.get_solo().fine_per_day
        return rate * self.days_overdue


class Fine(models.Model):
    """A recorded library fine — late return, lost or damaged copy (spec §20)."""

    issue = models.ForeignKey(
        Issue,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="fines",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.issue or 'Standalone'} — ₹{self.amount}"