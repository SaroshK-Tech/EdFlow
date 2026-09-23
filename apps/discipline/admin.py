from django.contrib import admin

from .models import Achievement, Action, FollowUp, Incident, Warning


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("student", "title", "date", "type", "severity", "status", "klass")
    list_filter = ("severity", "status", "type", "klass")
    search_fields = (
        "title",
        "student__admission_number",
        "student__first_name",
        "student__last_name",
    )
    date_hierarchy = "date"


@admin.register(Warning)
class WarningAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "type", "issued_by", "follow_up_required")
    list_filter = ("type", "follow_up_required")
    search_fields = (
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "issued_by",
    )


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "kind", "start_date", "end_date", "completed")
    list_filter = ("kind", "completed")
    search_fields = (
        "student__admission_number",
        "student__first_name",
        "student__last_name",
    )


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "category", "title", "house_points")
    list_filter = ("category",)
    search_fields = (
        "title",
        "student__admission_number",
        "student__first_name",
        "student__last_name",
    )


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("incident", "due_date", "completed", "owner", "created_at")
    list_filter = ("completed",)
    search_fields = ("incident__title", "owner")