import datetime

from django.db import models
from django.utils import timezone


class InquiryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONTACTED = "contacted", "Contacted"
    INTERVIEW = "interview", "Interview"
    OFFERED = "offered", "Offered"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    ENROLLED = "enrolled", "Enrolled"


class DocumentType(models.TextChoices):
    BIRTH_CERTIFICATE = "birth_certificate", "Birth Certificate"
    REPORT_CARD = "report_card", "Previous Report Card"
    TRANSFER_CERTIFICATE = "transfer_certificate", "Transfer Certificate"
    PASSPORT_PHOTO = "passport_photo", "Passport Photos"
    HEALTH_RECORDS = "health_records", "Health / Immunisation Records"
    OTHER = "other", "Other"


class AdmissionInquiry(models.Model):
    """Admission workflow entry point (spec §7)."""

    inquiry_number = models.CharField(max_length=50, unique=True, blank=True)
    student_first_name = models.CharField(max_length=100)
    student_last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    klass = models.ForeignKey(
        "academics.Class",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admission_inquiries",
    )
    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=12, choices=InquiryStatus.choices, default=InquiryStatus.PENDING
    )

    # Application / profile (spec §7: applicant profile)
    previous_school = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)
    applied_on = models.DateField(
        null=True, blank=True, help_text="Date the application was submitted."
    )

    # Interview / test (spec §7)
    interview_date = models.DateTimeField(null=True, blank=True)
    test_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    interview_notes = models.TextField(blank=True)

    # Decision (spec §7: approval/rejection)
    decision_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admission_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    # Enrollment (spec §7: admission number, class/section, fee setup, enrollment)
    enrollment = models.OneToOneField(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admission_inquiry",
    )
    enrolled_at = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Admission Inquiries"

    def save(self, *args, **kwargs):
        if not self.inquiry_number:
            today = datetime.date.today()
            prefix = f"INQ-{today:%Y%m%d}"
            last = (
                AdmissionInquiry.objects.filter(inquiry_number__startswith=prefix)
                .order_by("-inquiry_number")
                .first()
            )
            seq = 1
            if last and last.inquiry_number and len(last.inquiry_number) > len(prefix):
                seq = int(last.inquiry_number[len(prefix) + 1:]) + 1
            self.inquiry_number = f"{prefix}-{seq:03d}"
        super().save(*args, **kwargs)

    @property
    def applicant_name(self):
        return " ".join(p for p in (self.student_first_name, self.student_last_name) if p)

    @property
    def workflow_status(self):
        """Steps of the §7 workflow, each marked done/active/upcoming."""
        icons = {
            "inquiry": "bi-inbox",
            "application": "bi-file-earmark-person",
            "documents": "bi-paperclip",
            "interview": "bi-chat-dots",
            "decision": "bi-check2-circle",
            "enrollment": "bi-person-plus",
            "fees": "bi-credit-card",
            "done": "bi-award",
        }
        steps = []
        s = self.status

        steps.append(
            {
                "key": "inquiry",
                "icon": icons["inquiry"],
                "label": "Inquiry received",
                "done": True,
                "active": False,
                "detail": self.created_at.strftime("%d %b %Y"),
            }
        )

        steps.append(
            {
                "key": "application",
                "icon": icons["application"],
                "label": "Application & profile",
                "done": self.applied_on is not None,
                "active": self.applied_on is None and s in ("pending", "contacted"),
                "detail": self.applied_on.strftime("%d %b %Y") if self.applied_on else "Application form collected",
            }
        )

        steps.append(
            {
                "key": "documents",
                "icon": icons["documents"],
                "label": "Document collection",
                "done": self.documents.exists(),
                "active": not self.documents.exists(),
                "detail": f"{self.documents.count()} document(s)" if self.documents.exists() else "Upload certificates etc.",
            }
        )

        steps.append(
            {
                "key": "interview",
                "icon": icons["interview"],
                "label": "Interview / test",
                "done": self.interview_date is not None,
                "active": self.interview_date is None and s in ("contacted", "interview"),
                "detail": self.interview_date.strftime("%d %b %Y, %I:%M %p") if self.interview_date else "Schedule or record",
            }
        )

        done_decision = s in ("offered", "accepted", "enrolled")
        steps.append(
            {
                "key": "decision",
                "icon": icons["decision"],
                "label": "Approval / rejection",
                "done": done_decision or s in ("rejected", "enrolled"),
                "active": s == "offered",
                "detail": ("Offered" if done_decision else "Rejected" if s == "rejected" else "Approve or reject"),
            }
        )

        steps.append(
            {
                "key": "enrollment",
                "icon": icons["enrollment"],
                "label": "Enrollment (admission no + class)",
                "done": self.enrollment_id is not None,
                "active": self.enrollment_id is None and s in ("offered", "accepted"),
                "detail": (
                    f"{self.enrollment.admission_number}" if self.enrollment_id else "Generate admission number"
                ),
                "action": (
                    None
                    if self.enrollment_id or s not in ("offered", "accepted")
                    else (f"/admissions/{self.pk}/enroll/", "Enroll")
                ),
            }
        )

        steps.append(
            {
                "key": "fees",
                "icon": icons["fees"],
                "label": "Fee setup",
                "done": self.enrollment_id is not None and self.enrollment.vouchers.exists(),
                "active": False,
                "detail": (
                    f"{self.enrollment.vouchers.count()} voucher(s)"
                    if self.enrollment_id
                    else "After enrollment"
                ),
            }
        )

        steps.append(
            {
                "key": "done",
                "icon": icons["done"],
                "label": "Receipt, ID card & reports",
                "done": self.enrollment_id is not None,
                "active": False,
                "detail": "Available on student profile" if self.enrollment_id else "On completion",
            }
        )
        return steps

    def __str__(self):
        return self.inquiry_number or self.applicant_name


class AdmissionDocument(models.Model):
    """A collected applicant document (spec §7 document collection)."""

    inquiry = models.ForeignKey(
        AdmissionInquiry,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    doc_type = models.CharField(
        max_length=30, choices=DocumentType.choices, default=DocumentType.OTHER
    )
    file = models.FileField(upload_to="admissions/docs/", blank=True)
    note = models.CharField(max_length=200, blank=True)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.inquiry.inquiry_number} — {self.get_doc_type_display()}"