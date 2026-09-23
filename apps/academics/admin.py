from django.contrib import admin

from .models import Homework, Section, Subject, SubjectAllocation, Submission, Syllabus


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


class SubjectAllocationInline(admin.TabularInline):
    model = SubjectAllocation
    extra = 0


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "klass", "section", "subject", "teacher", "due_date")
    list_filter = ("kind", "klass", "subject", "due_date")
    search_fields = ("title", "description")
    autocomplete_fields = ("teacher",)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("homework", "student", "status", "submitted_on", "marks", "graded_by")
    list_filter = ("status", "homework__kind")
    search_fields = ("homework__title", "student__admission_number", "student__first_name")


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    list_display = ("title", "klass", "subject", "term", "start_date", "end_date")
    list_filter = ("klass", "subject", "term")
    search_fields = ("title",)