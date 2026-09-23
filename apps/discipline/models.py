import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class IncidentType(models.TextChoices):
    MISBEHAVIOR = "misbehavior", "Misbehavior"
    BULLYING = "bullying", "Bullying"
    ATTENDANCE = "attendance", "Attendance"
    VIOLATION = "violation", "Violation"
    OTHER = "other", "Other"


class IncidentSeverity(models.TextChoices):
    MINOR = "minor", "Minor"
    MODERATE = "moderate", "Moderate"
    SEVERE = "severe", "Severe"


class IncidentStatus(models.TextChoices):
    OPEN = "open", "Open"
    UNDER_REVIEW = "under_review", "Under Review"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class WarningType(models.TextChoices):
    VERBAL = "verbal", "Verbal"
    WRITTEN = "written", "Written"
    FINAL = "final", "Final"


class ActionKind(models.TextChoices):
    DETENTION = "detention", "Detention"
    SUSPENSION = "suspension", "Suspension"
    IMPROVEMENT_PLAN = "improvement_plan", "Improvement Plan"
    PARENT_CALL = "parent_call", "Parent Call"
    OTHER = "other", "Other"


class AchievementCategory(models.TextChoices):
    ACADEMIC = "academic", "Academic"
    SPORTS = "sports", "Sports"
    CULTURAL = "cultural", "Cultural"
    OTHER = "other", "Other"


class Incident(models.Model):
    """A reported discipline incident against a student (spec §18)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="incidents"
    )
    date = models.DateField(default=datetime.date.today)
    type = models.CharField(
        max_length=20, choices=IncidentType.choices, default=IncidentType.MISBEHAVIOR
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    severity = models.CharField(
        max_length=20, choices=IncidentSeverity.choices, default=IncidentSeverity.MINOR
    )
    status = models.CharField(
        max_length=20, choices=IncidentStatus.choices, default=IncidentStatus.OPEN
    )
    klass = models.ForeignKey(
        "academics.Class",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incidents",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incidents_reported",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["student", "date"]),
            models.Index(fields=["status", "severity"]),
            models.Index(fields=["klass", "date"]),
        ]

    def __str__(self):
        return f"{self.student} — {self.title} ({self.date:%Y-%m-%d})"

    @property
    def open_followups(self):
        return self.followups.filter(completed=False)


class Warning(models.Model):
    """A behavioural warning issued to a student (spec §18)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="warnings"
    )
    incident = models.ForeignKey(
        Incident,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warnings",
    )
    date = models.DateField(default=datetime.date.today)
    type = models.CharField(
        max_length=20, choices=WarningType.choices, default=WarningType.VERBAL
    )
    details = models.TextField(blank=True)
    issued_by = models.CharField(max_length=200, blank=True)
    follow_up_required = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student} — {self.get_type_display()} warning ({self.date:%Y-%m-%d})"


class Action(models.Model):
    """A disciplinary action taken against a student (spec §18)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="discipline_actions"
    )
    date = models.DateField(default=datetime.date.today)
    kind = models.CharField(
        max_length=30, choices=ActionKind.choices, default=ActionKind.DETENTION
    )
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student} — {self.get_kind_display()} ({self.date:%Y-%m-%d})"


class Achievement(models.Model):
    """A positive achievement earning house points (spec §18)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="achievements"
    )
    date = models.DateField(default=datetime.date.today)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    house_points = models.PositiveIntegerField(default=0)
    category = models.CharField(
        max_length=20, choices=AchievementCategory.choices, default=AchievementCategory.OTHER
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student} — {self.title}"


class FollowUp(models.Model):
    """A follow-up task linked to a discipline incident (spec §18)."""

    incident = models.ForeignKey(
        Incident, on_delete=models.CASCADE, related_name="followups"
    )
    note = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    owner = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["completed", "due_date", "-created_at"]

    def __str__(self):
        return f"Follow-up on {self.incident} ({self.created_at:%Y-%m-%d})"