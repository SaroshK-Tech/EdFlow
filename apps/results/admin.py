from django.contrib import admin

from .models import Result


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam",
        "percentage",
        "weighted_percentage",
        "grade",
        "class_position",
        "is_pass",
    )
    list_filter = ("exam", "is_pass")
    search_fields = ("student__admission_number", "student__first_name", "student__last_name")