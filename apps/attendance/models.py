import datetime

from django.db import models


class AttendanceStatus(models.TextChoices):
    PRESENT = "present", "Present"
    ABSENT = "absent", "Absent"
    LATE = "late", "Late"
    LEAVE = "leave", "Leave"
    EXCUSED = "excused", "Excused"


class StudentAttendance(models.Model):
    """Daily student attendance; optional per-period detail (spec §11)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="attendance"
    )
    date = models.DateField(default=datetime.date.today)
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    period = models.ForeignKey(
        "academics.Period",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records",
    )
    remarks = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="attendance_recorded",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date", "period"],
                name="unique_student_day_period",
            )
        ]
        verbose_name = "Student Attendance"
        verbose_name_plural = "Student Attendance"

    def __str__(self):
        return f"{self.student} — {self.date} — {self.get_status_display()}"


class PeriodAttendance(models.Model):
    """Per-period (subject) student attendance (spec §11)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="period_attendance"
    )
    date = models.DateField(default=datetime.date.today)
    period = models.ForeignKey(
        "academics.Period", on_delete=models.CASCADE, related_name="period_attendance"
    )
    subject = models.ForeignKey(
        "academics.Subject",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="period_attendance",
    )
    klass = models.ForeignKey(
        "academics.Class",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="period_attendance",
    )
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    marked_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="period_attendance_marked",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "period__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date", "period"],
                name="unique_period_attendance",
            )
        ]
        verbose_name = "Period Attendance"
        verbose_name_plural = "Period Attendance"

    def __str__(self):
        return f"{self.student} — {self.date} — {self.period} — {self.get_status_display()}"


class StaffAttendanceStatus(models.TextChoices):
    PRESENT = "present", "Present"
    ABSENT = "absent", "Absent"
    LATE = "late", "Late"
    LEAVE = "leave", "Leave"
    HALF_DAY = "half_day", "Half-day"


class StaffAttendance(models.Model):
    """Daily staff attendance with check-in/out and overtime (spec §11)."""

    staff = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="attendance"
    )
    date = models.DateField(default=datetime.date.today)
    status = models.CharField(max_length=12, choices=StaffAttendanceStatus.choices)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    overtime_minutes = models.PositiveIntegerField(default=0)
    remark = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="staff_attendance_marked",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "staff__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "date"], name="unique_staff_day"
            )
        ]
        verbose_name = "Staff Attendance"
        verbose_name_plural = "Staff Attendance"

    def __str__(self):
        return f"{self.staff} — {self.date} — {self.get_status_display()}"