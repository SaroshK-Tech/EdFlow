from django.conf import settings
from django.db import models
from django.utils import timezone


class AcademicLevel(models.TextChoices):
    PRE_PRIMARY = "pre_primary", "Pre-Primary"
    PRIMARY = "primary", "Primary"
    MIDDLE = "middle", "Middle"
    SECONDARY = "secondary", "Secondary"
    SENIOR_SECONDARY = "senior_secondary", "Senior Secondary"


class Class(models.Model):
    """A class/grade, e.g. 'Grade 6' (spec §8)."""

    name = models.CharField(max_length=100, unique=True)
    level = models.CharField(
        max_length=20, choices=AcademicLevel.choices, blank=True
    )
    class_teacher = models.ForeignKey(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="classes_taught",
    )
    subjects = models.ManyToManyField(
        "academics.Subject", related_name="classes", blank=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Section(models.Model):
    """A section within a class, e.g. 'Grade 6 - A' (spec §8)."""

    klass = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="sections"
    )
    name = models.CharField(max_length=20)  # e.g. "A"
    room = models.ForeignKey(
        "academics.Room",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sections",
    )

    class Meta:
        unique_together = ("klass", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.klass} — {self.name}"


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Room(models.Model):
    """Physical room used by the timetable solver (spec §9)."""

    name = models.CharField(max_length=100, unique=True)
    capacity = models.PositiveIntegerField(default=0)
    room_type = models.CharField(max_length=50, blank=True)  # e.g. "lab", "classroom"

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Period(models.Model):
    """A timed slot in the school day (spec §3, §9)."""

    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} ({self.start_time}–{self.end_time})"


class SubjectAllocation(models.Model):
    """How many periods of a subject a class/section is required to have."""

    klass = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="subject_allocations"
    )
    section = models.ForeignKey(
        Section,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subject_allocations",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="allocations"
    )
    teacher = models.ForeignKey(
        "staff.Staff",
        on_delete=models.CASCADE,
        related_name="subject_allocations",
    )
    periods_per_week = models.PositiveIntegerField(default=1)
    requires_lab = models.BooleanField(default=False)

    class Meta:
        ordering = ["klass", "section", "subject"]
        verbose_name_plural = "Subject Allocations"

    def __str__(self):
        where = f"{self.klass}" + (f" {self.section}" if self.section else "")
        return f"{where} — {self.subject} ({self.periods_per_week}/wk)"


class HomeworkKind(models.TextChoices):
    HOMEWORK = "homework", "Homework"
    ASSIGNMENT = "assignment", "Assignment"


class Homework(models.Model):
    """Task or assignment set for a class/section with a deadline (spec §19)."""

    title = models.CharField(max_length=200)
    description = models.TextField()
    klass = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="homeworks"
    )
    section = models.ForeignKey(
        Section,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="homeworks",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="homeworks"
    )
    teacher = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="homeworks"
    )
    due_date = models.DateField()
    kind = models.CharField(
        max_length=12,
        choices=HomeworkKind.choices,
        default=HomeworkKind.HOMEWORK,
    )
    attachments = models.FileField(upload_to="homework/", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def submitted_count(self):
        return self.submissions.count()


class SubmissionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUBMITTED = "submitted", "Submitted"
    GRADED = "graded", "Graded"
    LATE = "late", "Late"


class Submission(models.Model):
    """A student's submission for a homework/assignment (spec §19)."""

    homework = models.ForeignKey(
        Homework, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="submissions"
    )
    submitted_on = models.DateTimeField(default=timezone.now)
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to="submissions/", blank=True)
    marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.SUBMITTED,
    )
    teacher_remark = models.CharField(max_length=300, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="graded_submissions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["homework", "student"], name="unique_homework_submission"
            )
        ]
        ordering = ["-submitted_on"]

    def __str__(self):
        return f"{self.student} — {self.homework}"


class Syllabus(models.Model):
    """Syllabus/curriculum plan for a class and subject (spec §8)."""

    klass = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="syllabi"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="syllabi"
    )
    term = models.ForeignKey(
        "school.Term",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="syllabi",
    )
    title = models.CharField(max_length=200)
    units = models.JSONField(default=list, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_syllabi",
    )

    class Meta:
        ordering = ["klass", "subject", "title"]
        verbose_name_plural = "Syllabi"

    def __str__(self):
        return f"{self.klass} — {self.subject}: {self.title}"