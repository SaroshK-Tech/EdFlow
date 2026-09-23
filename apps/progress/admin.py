from django.contrib import admin

from .models import ProgressRecord


@admin.register(ProgressRecord)
class ProgressRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "category", "subject", "score", "term", "year", "created_at")
    list_filter = ("category", "term", "year", "subject")
    search_fields = (
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "remark",
    )
    date_hierarchy = "created_at"