from django.contrib import admin

from .models import (
    TeacherAvailability,
    TeacherPreference,
    Timetable,
    TimetableEntry,
)


class TimetableEntryInline(admin.TabularInline):
    model = TimetableEntry
    extra = 0


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ("name", "academic_year", "term", "status", "created_by", "created_at")
    list_filter = ("status", "academic_year")
    inlines = [TimetableEntryInline]


@admin.register(TeacherAvailability)
class TeacherAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("teacher", "weekday", "available")
    list_filter = ("weekday", "available")
    search_fields = ("teacher__first_name", "teacher__last_name", "teacher__employee_code")


@admin.register(TeacherPreference)
class TeacherPreferenceAdmin(admin.ModelAdmin):
    list_display = ("teacher", "subject", "after_lunch")
    list_filter = ("after_lunch",)
    search_fields = ("teacher__first_name", "teacher__last_name", "teacher__employee_code")