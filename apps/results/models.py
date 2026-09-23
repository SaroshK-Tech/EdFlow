from django.db import models


class Result(models.Model):
    """Computed examination result for one student (spec §14).

    Regenerated from ``exams.Mark`` rows; approved/published via the parent
    exam's status.
    """

    exam = models.ForeignKey(
        "exams.Exam", on_delete=models.CASCADE, related_name="results"
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="results"
    )
    total_max = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_obtained = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    weighted_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Cumulative % across exams weighted by exam-type weightage.",
    )
    grade = models.CharField(max_length=10, blank=True)
    gpa = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    class_position = models.PositiveIntegerField(null=True, blank=True)
    is_pass = models.BooleanField(default=False)
    remarks = models.CharField(max_length=200, blank=True)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam", "student")
        ordering = ["class_position", "student__admission_number"]

    def __str__(self):
        return f"{self.student} — {self.exam} ({self.percentage}%)"

    @property
    def subjects_count(self):
        return self.exam.subjects.filter(klass=self.student.klass).count()
