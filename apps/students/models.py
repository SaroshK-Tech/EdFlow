from django.conf import settings
from django.db import models
from django.utils import timezone


class Status(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    LEFT = "left", "Left"
    GRADUATED = "graduated", "Graduated"
    SUSPENDED = "suspended", "Suspended"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


class Student(models.Model):
    """Complete 360-degree student profile (spec §5)."""

    admission_number = models.CharField(max_length=50, unique=True)
    # nullable so multiple students may leave it unset (unique allows many NULLs)
    registration_number = models.CharField(
        max_length=50, blank=True, null=True, unique=True
    )
    roll_number = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    photograph = models.ImageField(upload_to="students/", blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    religion = models.CharField(max_length=50, blank=True)
    nationality = models.CharField(max_length=50, blank=True)

    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    house = models.ForeignKey(
        "houses.House",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
    )
    klass = models.ForeignKey(
        "academics.Class",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
        verbose_name="Class",
    )
    section = models.ForeignKey(
        "academics.Section",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.ACTIVE
    )

    previous_school = models.CharField(max_length=200, blank=True)
    medical_notes = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    joined_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["roll_number", "first_name"]
        indexes = [
            models.Index(fields=["admission_number"]),
            models.Index(fields=["klass", "section"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Student"
        verbose_name_plural = "Students"

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.middle_name, self.last_name) if p)

    def __str__(self):
        return f"{self.admission_number} — {self.full_name}"