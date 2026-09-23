import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import (
    AdmissionDecisionForm,
    AdmissionDocumentForm,
    AdmissionInquiryForm,
    EnrollmentForm,
)
from .models import AdmissionDocument, AdmissionInquiry


class AdmissionListView(EdFlowMixin, SearchMixin, ListView):
    model = AdmissionInquiry
    template_name = "admissions/inquiry_list.html"
    context_object_name = "inquiries"
    paginate_by = 25
    page_title = "Admissions"
    page_subtitle = "Inquiries, applications and enrollment status"
    active_page = "admissions"
    search_fields = [
        "inquiry_number",
        "student_first_name",
        "student_last_name",
        "guardian_name",
        "guardian_phone",
    ]
    search_placeholder = "Search by inquiry no, name, guardian…"

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return qs.select_related("klass", "enrollment")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total"] = AdmissionInquiry.objects.count()
        ctx["pending"] = AdmissionInquiry.objects.filter(status="pending").count()
        ctx["enrolled"] = AdmissionInquiry.objects.filter(status="enrolled").count()
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = AdmissionInquiry._meta.get_field("status").choices
        return ctx


class AdmissionDetailView(EdFlowMixin, DetailView):
    model = AdmissionInquiry
    template_name = "admissions/inquiry_detail.html"
    context_object_name = "inquiry"
    active_page = "admissions"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        inquiry = self.object
        ctx["page_title"] = f"Admission — {inquiry.applicant_name}"
        ctx["page_subtitle"] = inquiry.inquiry_number
        ctx["document_form"] = AdmissionDocumentForm()
        ctx["decision_form"] = AdmissionDecisionForm(
            initial={"interview_date": inquiry.interview_date, "test_score": inquiry.test_score}
        )
        return ctx


class AdmissionCreateView(EdFlowMixin, CreateView):
    model = AdmissionInquiry
    form_class = AdmissionInquiryForm
    template_name = "admissions/inquiry_form.html"
    page_title = "New Admission Inquiry"
    active_page = "admissions"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"admission.create {self.object.inquiry_number}")
        messages.success(
            self.request, f"Inquiry {self.object.inquiry_number} created."
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("admissions:detail", args=[self.object.pk])


class AdmissionUpdateView(EdFlowMixin, UpdateView):
    model = AdmissionInquiry
    form_class = AdmissionInquiryForm
    template_name = "admissions/inquiry_form.html"
    context_object_name = "inquiry"
    page_title = "Update Admission Inquiry"
    active_page = "admissions"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"admission.update {self.object.inquiry_number}")
        messages.success(
            self.request, f"Inquiry {self.object.inquiry_number} updated."
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("admissions:detail", args=[self.object.pk])


class AdmissionDecisionView(EdFlowMixin, FormView):
    """Approve (→ Offered) or reject an application (§7)."""

    form_class = AdmissionDecisionForm
    http_method_names = ["post"]

    def get_inquiry(self):
        return get_object_or_404(AdmissionInquiry, pk=self.kwargs["pk"])

    def form_valid(self, form):
        inquiry = self.get_inquiry()
        data = form.cleaned_data
        if data.get("interview_date"):
            inquiry.interview_date = data["interview_date"]
        if data.get("test_score") is not None:
            inquiry.test_score = data["test_score"]
        if data.get("interview_notes"):
            inquiry.interview_notes = data["interview_notes"]
        if data["decision"] == "accept":
            inquiry.status = "offered"
            messages.success(
                self.request,
                f"{inquiry.applicant_name} approved — status is now Offered.",
            )
            audit(self.request, f"admission.accept {inquiry.inquiry_number}")
        else:
            inquiry.status = "rejected"
            messages.success(
                self.request,
                f"{inquiry.applicant_name} rejected. Send feedback via Communication.",
            )
            audit(self.request, f"admission.reject {inquiry.inquiry_number}")
        inquiry.decision_by = self.request.user
        inquiry.decided_at = timezone.now()
        inquiry.save()
        return redirect("admissions:detail", pk=inquiry.pk)


class AdmissionDocumentCreateView(EdFlowMixin, FormView):
    """Collect a document for an inquiry (§7 document collection)."""

    form_class = AdmissionDocumentForm
    http_method_names = ["post"]

    def get_inquiry(self):
        return get_object_or_404(AdmissionInquiry, pk=self.kwargs["pk"])

    def form_valid(self, form):
        inquiry = self.get_inquiry()
        doc = form.save(commit=False)
        doc.inquiry = inquiry
        doc.save()
        audit(self.request, f"admission.document_add {inquiry.inquiry_number} {doc.get_doc_type_display()}")
        messages.success(self.request, f"Document '{doc.get_doc_type_display()}' recorded.")
        return redirect("admissions:detail", pk=inquiry.pk)


class AdmissionDocumentDeleteView(EdFlowMixin, DeleteView):
    model = AdmissionDocument
    context_object_name = "document"

    def get_success_url(self):
        inquiry = self.object.inquiry
        audit(self.request, f"admission.document_del {self.object.inquiry.inquiry_number}")
        messages.success(self.request, "Document removed.")
        return reverse("admissions:detail", args=[inquiry.pk])


class AdmissionEnrollView(EdFlowMixin, FormView):
    """Enroll an accepted applicant: student record + admission number + fee setup (§7)."""

    form_class = EnrollmentForm
    template_name = "admissions/enroll.html"
    active_page = "admissions"

    def get_inquiry(self):
        return get_object_or_404(AdmissionInquiry, pk=self.kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        inquiry = self.get_inquiry()
        if inquiry.enrollment_id:
            messages.info(request, "This applicant is already enrolled.")
            return redirect("admissions:detail", pk=inquiry.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_page_title(self):
        return f"Enroll {self.get_inquiry().applicant_name}"

    def get_context_data(self, **kwargs):
        inquiry = self.get_inquiry()
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = f"Enroll {inquiry.applicant_name}"
        ctx["page_subtitle"] = f"{inquiry.inquiry_number} · class {inquiry.klass}"
        ctx["inquiry"] = inquiry
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        inquiry = self.get_inquiry()
        kwargs["initial"].update(
            {
                "klass_id": inquiry.klass_id,
                "admission_number": self._next_admission_number(),
                "joined_at": datetime.date.today(),
            }
        )
        return kwargs

    def _next_admission_number(self):
        from apps.students.models import Student

        year = datetime.date.today().year
        prefix = f"ADM-{year}-"
        last = (
            Student.objects.filter(admission_number__startswith=prefix)
            .order_by("-admission_number")
            .first()
        )
        seq = 1
        if last and len(last.admission_number) > len(prefix):
            try:
                seq = int(last.admission_number[len(prefix):]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{seq:04d}"

    def form_valid(self, form):
        inquiry = self.get_inquiry()
        data = form.cleaned_data
        from apps.academics.models import Section
        from apps.parents.models import Parent
        from apps.students.models import Student

        with transaction.atomic():
            student = Student.objects.create(
                admission_number=data["admission_number"],
                roll_number=data.get("roll_number") or "",
                first_name=inquiry.student_first_name,
                last_name=inquiry.student_last_name,
                date_of_birth=inquiry.date_of_birth,
                gender=inquiry.gender,
                klass=inquiry.klass,
                section=data.get("section") or None,
                joined_at=data["joined_at"],
                previous_school=inquiry.previous_school,
                address=inquiry.address,
                medical_notes=inquiry.medical_notes,
                status="active",
            )
            inquiry.enrollment = student
            inquiry.status = "enrolled"
            inquiry.enrolled_at = data["joined_at"]
            inquiry.save()

            # Guardianship from inquiry details.
            if inquiry.guardian_name:
                parent, _ = Parent.objects.get_or_create(
                    phone=inquiry.guardian_phone or None,
                    defaults={
                        "first_name": inquiry.guardian_name.split()[0],
                        "last_name": " ".join(inquiry.guardian_name.split()[1:]),
                        "email": inquiry.guardian_email,
                        "is_primary": True,
                    },
                )
                parent.students.add(student)

            # Fee setup: generate a voucher from active fee heads.
            voucher = None
            if data.get("create_fee_voucher"):
                from apps.fees.models import FeeHead, FeeVoucher, FeeVoucherItem

                heads = FeeHead.objects.filter(is_active=True)
                if heads.exists():
                    voucher = FeeVoucher.objects.create(student=student, status="issued")
                    for head in heads:
                        FeeVoucherItem.objects.create(
                            voucher=voucher, fee_head=head, amount=head.amount
                        )

        audit(
            self.request,
            f"admission.enroll {inquiry.inquiry_number} -> {student.admission_number}"
            + (f" voucher={voucher.voucher_number}" if voucher else ""),
        )
        messages.success(
            self.request,
            f"{student.full_name} enrolled as {student.admission_number}. "
            + ("Fee voucher generated." if voucher else "No active fee heads — add them under Fees."),
        )
        return redirect("admissions:detail", pk=inquiry.pk)

    def get_success_url(self):
        return reverse_lazy("admissions:detail", args=[self.kwargs["pk"]])


class AdmissionReportsView(EdFlowMixin, TemplateView):
    template_name = "admissions/reports.html"
    page_title = "Admission Reports"
    page_subtitle = "Pipeline, class-wise demand and admission trends (spec §7)"
    active_page = "admissions"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Count, Q

        ctx["total"] = AdmissionInquiry.objects.count()
        by_status = list(
            AdmissionInquiry.objects.values("status")
            .annotate(total=Count("id"))
            .order_by("status")
        )
        ctx["by_status"] = by_status
        ctx["status_map"] = dict(AdmissionInquiry._meta.get_field("status").choices)
        ctx["enrolled_count"] = AdmissionInquiry.objects.filter(status="enrolled").count()
        ctx["conversion"] = (
            round(ctx["enrolled_count"] / ctx["total"] * 100, 1) if ctx["total"] else 0
        )
        ctx["by_class"] = list(
            AdmissionInquiry.objects.exclude(klass=None)
            .values("klass__name")
            .annotate(
                total=Count("id"),
                enrolled=Count("id", filter=Q(status="enrolled")),
            )
            .order_by("-total")
        )
        from .models import AdmissionDocument

        ctx["documents_count"] = AdmissionDocument.objects.count()
        return ctx