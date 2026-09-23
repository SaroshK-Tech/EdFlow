from django.contrib import admin

from .models import AcademicYear, Holiday, SchoolProfile, Term, WorkingDay


@admin.register(SchoolProfile)
class SchoolProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "established_year")


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("name", "academic_year", "start_date", "end_date", "is_active")


@admin.register(WorkingDay)
class WorkingDayAdmin(admin.ModelAdmin):
    list_display = ("academic_year", "weekday")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("name", "academic_year", "start_date", "end_date")
    date_hierarchy = "start_date"