from django.contrib import admin

from .models import PeriodAttendance, StaffAttendance, StudentAttendance


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "period", "status", "recorded_by")
    list_filter = ("date", "status")
    search_fields = ("student__admission_number", "student__first_name", "student__last_name")
    date_hierarchy = "date"


@admin.register(PeriodAttendance)
class PeriodAttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "period", "subject", "klass", "status", "marked_by")
    list_filter = ("date", "status", "subject", "klass")
    search_fields = ("student__admission_number", "student__first_name", "student__last_name")
    date_hierarchy = "date"


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ("staff", "date", "status", "check_in", "check_out", "overtime_minutes")
    list_filter = ("date", "status")
    search_fields = ("staff__employee_code", "staff__first_name", "staff__last_name")
    date_hierarchy = "date"
