from django.contrib import admin

from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "full_name",
        "designation",
        "department",
        "is_teacher",
        "status",
    )
    list_filter = ("is_teacher", "status", "department")
    search_fields = ("employee_code", "first_name", "middle_name", "last_name", "phone")