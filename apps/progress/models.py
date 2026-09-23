from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class ProgressCategory(models.TextChoices):
    ASSESSMENT = "assessment", "Assessment"
    HOMEWORK = "homework", "Homework"
    BEHAVIOR = "behavior", "Behavior"
    SKILL = "skill", "Skill"
    LEARNING_OUTCOME = "learning_outcome", "Learning Outcome"


class ProgressRecord(models.Model):
    """A point-in-time student progress note (spec §10)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="progress_records"
    )
    term = models.ForeignKey(
        "school.Term",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_records",
    )
    year = models.ForeignKey(
        "school.AcademicYear",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_records",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_records",
    )
    category = models.CharField(
        max_length=30,
        choices=ProgressCategory.choices,
        default=ProgressCategory.ASSESSMENT,
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    remark = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_records_created",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["student", "category"]),
            models.Index(fields=["student", "year", "term"]),
        ]

    def __str__(self):
        where = self.subject or self.get_category_display()
        return f"{self.student} — {where} ({self.score}%)"