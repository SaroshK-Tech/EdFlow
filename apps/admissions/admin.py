from django.contrib import admin

from .models import AdmissionDocument, AdmissionInquiry


@admin.register(AdmissionInquiry)
class AdmissionInquiryAdmin(admin.ModelAdmin):
    list_display = (
        "inquiry_number",
        "student_first_name",
        "student_last_name",
        "klass",
        "guardian_phone",
        "status",
        "enrollment",
        "decided_at",
        "created_at",
    )
    list_filter = ("status", "created_at", "decided_at")
    search_fields = (
        "inquiry_number",
        "student_first_name",
        "student_last_name",
        "guardian_name",
        "guardian_phone",
        "guardian_email",
    )
    readonly_fields = ("inquiry_number", "enrolled_at", "decided_at", "enrollment")


@admin.register(AdmissionDocument)
class AdmissionDocumentAdmin(admin.ModelAdmin):
    list_display = ("inquiry", "doc_type", "note", "received_at")
    list_filter = ("doc_type", "received_at")
    search_fields = ("inquiry__inquiry_number", "inquiry__student_first_name", "note")