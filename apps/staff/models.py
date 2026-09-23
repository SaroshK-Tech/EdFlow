import datetime

from django.db import models
from django.utils import timezone

from apps.students.models import Status


class Staff(models.Model):
    """Employee/staff profile (spec §16, shared by teaching and non-teaching)."""

    employee_code = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    photograph = models.ImageField(upload_to="staff/", blank=True)

    gender = models.CharField(
        max_length=10,
        choices=(
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ),
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    department = models.ForeignKey(
        "hr.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    designation = models.CharField(max_length=100, blank=True)
    is_teacher = models.BooleanField(default=False)
    joining_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name = "Staff"
        verbose_name_plural = "Staff"

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.middle_name, self.last_name) if p)

    def __str__(self):
        return f"{self.employee_code} — {self.full_name}"

    @property
    def years_of_service(self):
        if not self.joining_date:
            return None
        days = (timezone.localdate() - self.joining_date).days
        return max(days / 365, 0)


class StaffDocument(models.Model):
    """Document attached to a staff record (spec §16 'Documents')."""

    DOCUMENT_TYPES = [
        ("qualification", "Qualification certificate"),
        ("id_proof", "ID / proof"),
        ("contract", "Contract"),
        ("appointment", "Appointment letter"),
        ("other", "Other"),
    ]

    staff = models.ForeignKey(
        Staff, on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=150)
    document_type = models.CharField(
        max_length=20, choices=DOCUMENT_TYPES, default="other"
    )
    file = models.FileField(upload_to="staff_documents/")
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_documents_uploaded",
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.staff} — {self.title}"