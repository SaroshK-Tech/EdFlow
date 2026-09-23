from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class GradeBoundary(models.Model):
    """Grade + GPA + remark mapping for a percentage band (spec §14)."""

    name = models.CharField(max_length=10)  # A+, A, B, ...
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    gpa = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    remark = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-min_percentage"]
        verbose_name = "Grade Boundary"
        verbose_name_plural = "Grade Boundaries"

    def clean(self):
        if (
            self.min_percentage is not None
            and self.max_percentage is not None
            and self.max_percentage < self.min_percentage
        ):
            raise ValidationError("Max percentage must be greater than or equal to min.")

    def __str__(self):
        return f"{self.name} ({self.min_percentage}–{self.max_percentage}%)"

    @classmethod
    def for_percentage(cls, percentage):
        if percentage is None:
            return None
        return (
            cls.objects.filter(
                min_percentage__lte=percentage, max_percentage__gte=percentage
            )
            .order_by("-min_percentage")
            .first()
        )


class ExamType(models.Model):
    """Category of assessment, e.g. Unit Test, Mid Term, Final (spec §14)."""

    name = models.CharField(max_length=100, unique=True)
    weightage = models.DecimalField(
        max_digits=5, decimal_places=2, default=100,
        help_text="Relative weight of this exam type in aggregates.",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExamStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"


class Exam(models.Model):
    """A scheduled examination (spec §14)."""

    name = models.CharField(max_length=150)
    exam_type = models.ForeignKey(
        ExamType, on_delete=models.PROTECT, related_name="exams"
    )
    academic_year = models.ForeignKey(
        "school.AcademicYear",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exams",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=ExamStatus.choices, default=ExamStatus.DRAFT
    )
    remarks = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-start_date", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.exam_type})"

    @property
    def is_published(self):
        return self.status == ExamStatus.PUBLISHED


class ExamSubject(models.Model):
    """A subject examined for a class within an exam (spec §14 'subjects')."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="subjects")
    klass = models.ForeignKey(
        "academics.Class", on_delete=models.CASCADE, related_name="exam_subjects"
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.CASCADE, related_name="exam_subjects"
    )
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    pass_marks = models.DecimalField(max_digits=6, decimal_places=2, default=33)
    weightage = models.DecimalField(
        max_digits=5, decimal_places=2, default=100,
        help_text="Weight of this subject in the exam aggregate.",
    )

    class Meta:
        unique_together = ("exam", "klass", "subject")
        ordering = ["klass", "subject__name"]
        verbose_name = "Exam Subject"
        verbose_name_plural = "Exam Subjects"

    def __str__(self):
        return f"{self.exam.name} — {self.klass} / {self.subject}"


class Mark(models.Model):
    """A student's mark for one exam subject (spec §14 'marks')."""

    exam_subject = models.ForeignKey(
        ExamSubject, on_delete=models.CASCADE, related_name="marks"
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="marks"
    )
    marks_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    is_absent = models.BooleanField(default=False)
    teacher_remark = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam_subject", "student")
        ordering = ["student__roll_number", "student__first_name"]

    def __str__(self):
        return f"{self.student} — {self.exam_subject.subject} ({self.marks_obtained})"

    @property
    def effective_marks(self):
        if self.is_absent or self.marks_obtained is None:
            return 0
        return self.marks_obtained

    @property
    def percentage(self):
        max_marks = self.exam_subject.max_marks
        if not max_marks:
            return 0
        return round(self.effective_marks * 100 / max_marks, 2)

    @property
    def grade(self):
        boundary = GradeBoundary.for_percentage(self.percentage)
        return boundary.name if boundary else ""

    @property
    def is_pass(self):
        return not self.is_absent and self.effective_marks >= self.exam_subject.pass_marks
