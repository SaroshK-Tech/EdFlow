from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.school.models import Weekday


class TimetableStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class Timetable(models.Model):
    """A full school timetable (versioned, spec §9)."""

    name = models.CharField(max_length=200)
    academic_year = models.ForeignKey(
        "school.AcademicYear", on_delete=models.CASCADE, related_name="timetables"
    )
    term = models.ForeignKey(
        "school.Term",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="timetables",
    )
    status = models.CharField(
        max_length=12,
        choices=TimetableStatus.choices,
        default=TimetableStatus.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="timetables_created",
    )
    constraints_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class TimetableEntry(models.Model):
    """A single scheduled cell: day × period → subject/teacher/room."""

    timetable = models.ForeignKey(
        Timetable, on_delete=models.CASCADE, related_name="entries"
    )
    weekday = models.CharField(max_length=1, choices=Weekday.choices)
    period = models.ForeignKey(
        "academics.Period",
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )
    klass = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    section = models.ForeignKey(
        "academics.Section",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    teacher = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    room = models.ForeignKey(
        "academics.Room", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    is_locked = models.BooleanField(
        default=False, help_text="Locked cells are preserved on regeneration."
    )

    class Meta:
        ordering = ["weekday", "period__order"]
        indexes = [
            models.Index(fields=["timetable", "weekday"]),
            models.Index(fields=["timetable", "teacher"]),
            models.Index(fields=["timetable", "room"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["timetable", "weekday", "period", "klass"],
                name="unique_timetable_cell",
            )
        ]

    def __str__(self):
        where = f"{self.klass}" + (f"/{self.section.name}" if self.section else "")
        return f"{self.timetable.name} {self.get_weekday_display()} P{self.period.order} {where} {self.subject}"

    def swap_with(self, other):
        """Atomically swap this entry's (weekday, period) with ``other``'s.

        A one-shot UPDATE ... CASE fails because SQLite enforces the unique
        index on (timetable, weekday, period, klass) after every row write.
        Instead we park ``self`` on a sentinel weekday (99, never a real
        school day) before moving the other entry, then move ``self`` into
        the freed slot. Runs inside a transaction so it is atomic.
        """
        table = self._meta.db_table
        fk_lookup = self._meta.get_field("period").column
        from django.db import connection, transaction

        self_weekday, other_weekday = self.weekday, other.weekday
        self_period_id, other_period_id = self.period_id, other.period_id
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    f"UPDATE {table} SET weekday=99 WHERE id=%s",
                    [self.pk],
                )
                cur.execute(
                    f"UPDATE {table} SET weekday=%s, {fk_lookup}=%s WHERE id=%s",
                    [self_weekday, self_period_id, other.pk],
                )
                cur.execute(
                    f"UPDATE {table} SET weekday=%s, {fk_lookup}=%s WHERE id=%s",
                    [other_weekday, other_period_id, self.pk],
                )
        self.weekday, other.weekday = other_weekday, self_weekday
        self.period_id, other.period_id = other_period_id, self_period_id


class TeacherAvailability(models.Model):
    """Per-weekday availability of a teacher for the scheduler (spec §9)."""

    teacher = models.ForeignKey(
        "staff.Staff",
        on_delete=models.CASCADE,
        related_name="timetable_availability",
    )
    weekday = models.CharField(max_length=1, choices=Weekday.choices)
    available = models.BooleanField(default=True)

    class Meta:
        ordering = ["teacher", "weekday"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "weekday"],
                name="unique_teacher_weekday",
            )
        ]
        verbose_name_plural = "Teacher availabilities"

    def __str__(self):
        return f"{self.teacher} {self.get_weekday_display()} available={self.available}"


class TeacherPreference(models.Model):
    """Soft scheduling preferences for the solver (after-lunch placement etc.)."""

    teacher = models.ForeignKey(
        "staff.Staff",
        on_delete=models.CASCADE,
        related_name="timetable_preferences",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="timetable_preferences",
    )
    after_lunch = models.BooleanField(
        default=False,
        help_text="Teacher prefers to teach this subject after lunch.",
    )

    class Meta:
        ordering = ["teacher", "subject"]

    def __str__(self):
        subject = self.subject or "any subject"
        return f"{self.teacher} {subject}" + (" after-lunch" if self.after_lunch else "")