from django.contrib import admin

from .models import DocumentTemplate, GeneratedDocument


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "doc_type", "is_active", "is_system")
    list_filter = ("doc_type", "is_active", "is_system")
    search_fields = ("name", "body")


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "doc_type", "student", "staff", "generated_by", "created_at")
    list_filter = ("doc_type",)
    search_fields = ("title", "student__first_name", "student__admission_number")