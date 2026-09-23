from django.contrib import admin

from .models import (
    Department,
    Designation,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "head_of_department")
    search_fields = ("name",)


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "grade")
    search_fields = ("name",)
    list_filter = ("department",)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "days_per_year", "paid")
    search_fields = ("name", "code")


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("staff", "leave_type", "year", "entitled", "used", "remaining")
    list_filter = ("year", "leave_type")
    search_fields = ("staff__first_name", "staff__employee_code")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("staff", "leave_type", "start_date", "end_date", "days", "status")
    list_filter = ("status", "leave_type")
    search_fields = ("staff__first_name", "staff__employee_code")