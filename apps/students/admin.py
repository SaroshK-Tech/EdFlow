from django.contrib import admin

from .forms import StudentForm
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentForm
    list_display = (
        "admission_number",
        "full_name",
        "klass",
        "section",
        "house",
        "status",
    )
    list_filter = ("status", "klass", "section", "house")
    search_fields = (
        "admission_number",
        "registration_number",
        "first_name",
        "middle_name",
        "last_name",
    )
    list_per_page = 50