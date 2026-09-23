from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    head_of_department = models.ForeignKey(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="departments_headed",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Qualification(models.Model):
    """An academic/professional qualification earned by a staff member
    (spec §16 'Qualifications')."""

    staff = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="qualifications"
    )
    qualification = models.CharField(max_length=150)  # e.g. "B.Ed (Science)"
    institution = models.CharField(max_length=200, blank=True)
    year_completed = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=50, blank=True)  # e.g. "First Class"
    is_certified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-year_completed", "qualification"]
        verbose_name = "Qualification"
        verbose_name_plural = "Qualifications"

    def __str__(self):
        return f"{self.staff} — {self.qualification}"


class Experience(models.Model):
    """Prior employment history for a staff member (spec §16 'Experience')."""

    staff = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="experiences"
    )
    organisation = models.CharField(max_length=200)
    job_title = models.CharField(max_length=150, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    current = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-start_date", "organisation"]
        verbose_name = "Experience"
        verbose_name_plural = "Experience"

    @property
    def years(self):
        if not self.start_date:
            return None
        end = self.end_date or timezone.localdate()
        if end < self.start_date:
            return 0
        return (end - self.start_date).days / 365

    def __str__(self):
        return f"{self.staff} — {self.job_title or self.organisation} ({self.organisation})"


class Designation(models.Model):
    """Job title attached to staff (spec §16)."""

    name = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="designations",
    )
    grade = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        from apps.staff.models import Staff

        return Staff.objects.filter(designation=self.name).count()


class LeaveType(models.Model):
    """A leave category (casual, sick, annual…) with its annual quota."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, unique=True)
    days_per_year = models.PositiveIntegerField(default=0)
    paid = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    """Annual leave entitlement/usage per staff member and type."""

    staff = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="leave_balances"
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.CASCADE, related_name="balances"
    )
    year = models.PositiveIntegerField()
    entitled = models.PositiveIntegerField(default=0)
    used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["year", "staff__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "leave_type", "year"],
                name="unique_leave_balance_staff_type_year",
            )
        ]

    @property
    def remaining(self):
        return self.entitled - self.used

    def __str__(self):
        return f"{self.staff} — {self.leave_type} {self.year}"


class LeaveStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class LeaveRequest(models.Model):
    """A staff member's leave application workflow."""

    staff = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="leave_requests"
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="requests"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=LeaveStatus.choices, default=LeaveStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leave_reviews",
    )
    reviewed_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return f"{self.staff} — {self.leave_type} ({self.days}d)"