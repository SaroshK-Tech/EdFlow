from django.contrib import admin

from .models import Parent

from apps.students.models import Student


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "relationship", "phone", "email", "is_primary")
    search_fields = ("first_name", "last_name", "phone", "email")
    filter_horizontal = ("students",)