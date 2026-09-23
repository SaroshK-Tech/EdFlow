from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Weekday(models.TextChoices):
    MONDAY = "1", "Monday"
    TUESDAY = "2", "Tuesday"
    WEDNESDAY = "3", "Wednesday"
    THURSDAY = "4", "Thursday"
    FRIDAY = "5", "Friday"
    SATURDAY = "6", "Saturday"
    SUNDAY = "7", "Sunday"


class SchoolProfile(models.Model):
    """V1 represents exactly ONE school (spec §3). Keep it a single row."""

    name = models.CharField(max_length=200)
    tagline = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to="school/", blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    established_year = models.PositiveIntegerField(null=True, blank=True)
    # Banking details printed on fee vouchers for offline payment by bank/UPI.
    bank_holder = models.CharField("Account Holder Name", max_length=200, blank=True)
    bank_name = models.CharField("Bank Name", max_length=200, blank=True)
    bank_branch = models.CharField("Branch", max_length=200, blank=True)
    bank_account_number = models.CharField("Account Number", max_length=50, blank=True)
    bank_ifsc = models.CharField("IFSC Code", max_length=20, blank=True)

    class Meta:
        verbose_name = "School Profile"
        verbose_name_plural = "School Profiles"

    def save(self, *args, **kwargs):
        if not self.pk and SchoolProfile.objects.exists():
            raise ValidationError(
                "EdFlow V1 supports a single school profile. Edit the "
                "existing one instead of creating a second."
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class AcademicYear(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. "2026/2027"
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date.")

    def __str__(self):
        return self.name


class Term(models.Model):
    name = models.CharField(max_length=50)  # e.g. "Term 1"
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="terms"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["start_date"]
        unique_together = ("academic_year", "name")

    def __str__(self):
        return f"{self.academic_year} — {self.name}"


class WorkingDay(models.Model):
    """School working days within an academic year (spec §3, §9)."""

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="working_days"
    )
    weekday = models.CharField(max_length=1, choices=Weekday.choices)

    class Meta:
        unique_together = ("academic_year", "weekday")
        ordering = ["weekday"]

    def __str__(self):
        return f"{self.academic_year} — {self.get_weekday_display()}"


class Holiday(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="holidays"
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.name} ({self.start_date} — {self.end_date})"