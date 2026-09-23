import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class DocumentType(models.TextChoices):
    STUDENT_ID = "student_id_card", "Student ID Card"
    STAFF_ID = "staff_id_card", "Staff ID Card"
    ADMISSION = "admission_letter", "Admission Letter"
    BONAFIDE = "bonafide_certificate", "Bonafide Certificate"
    CHARACTER = "character_certificate", "Character Certificate"
    LEAVING = "leaving_certificate", "Leaving Certificate"
    FEE_RECEIPT = "fee_receipt", "Fee Receipt"


class DocumentTemplate(models.Model):
    """Configurable document bodies (spec §23: templates should be editable)."""

    doc_type = models.CharField(max_length=30, choices=DocumentType.choices)
    name = models.CharField(max_length=120)
    body = models.TextField(
        help_text="Body text with placeholders like {student_name}, {admission_number}, "
        "{class_name}, {school_name}, {date}.",
        default="",
    )
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["doc_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_doc_type_display()})"


class GeneratedDocument(models.Model):
    """A produced document (PDF stored on the local server disk)."""

    doc_type = models.CharField(max_length=30, choices=DocumentType.choices)
    template = models.ForeignKey(
        DocumentTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )
    student = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_documents",
    )
    staff = models.ForeignKey(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_documents",
    )
    title = models.CharField(max_length=200)
    pdf = models.FileField(upload_to="documents/generated/", blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_documents",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_doc_type_display()})"

    def filename(self):
        stamp = self.created_at.strftime("%Y%m%d-%H%M%S")
        slug = slugify_title(self.title)
        return f"{slug}-{self.pk or 'x'}-{stamp}.pdf"


def slugify_title(value):
    keep = [c if c.isalnum() or c in " -_" else " " for c in value]
    slug = "".join(keep).strip()
    while "  " in slug:
        slug = slug.replace("  ", " ")
    return slug.replace(" ", "-").lower()