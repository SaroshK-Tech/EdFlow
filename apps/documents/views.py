import datetime

from django.contrib import messages
from django.http import Http404
from django.urls import reverse
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import (
    CertificateGenerateForm,
    DocumentTemplateForm,
    ReceiptGenerateForm,
    StaffGenerateForm,
    StudentGenerateForm,
)
from .models import DocumentTemplate, GeneratedDocument
from .services import (
    admission_pdf,
    certificate_pdf,
    fee_receipt_pdf,
    staff_id_pdf,
    student_id_pdf,
)

_DOC_META = {
    "student_id_card": {
        "title": "Student ID Card",
        "icon": "person-vcard",
        "form": StudentGenerateForm,
        "desc": "Generate a printable student identity card PDF.",
    },
    "staff_id_card": {
        "title": "Staff ID Card",
        "icon": "person-badge",
        "form": StaffGenerateForm,
        "desc": "Generate a printable staff identity card PDF.",
    },
    "admission_letter": {
        "title": "Admission Letter",
        "icon": "envelope-paper",
        "form": StudentGenerateForm,
        "desc": "Generate an admission confirmation letter PDF.",
    },
    "bonafide_certificate": {
        "title": "Bonafide Certificate",
        "icon": "patch-check",
        "form": CertificateGenerateForm,
        "desc": "Certificate stating the student is bonafide.",
    },
    "character_certificate": {
        "title": "Character Certificate",
        "icon": "award",
        "form": CertificateGenerateForm,
        "desc": "Certificate of student character and conduct.",
    },
    "leaving_certificate": {
        "title": "Leaving Certificate",
        "icon": "signpost-split",
        "form": CertificateGenerateForm,
        "desc": "Certificate issued on leaving the school.",
    },
    "fee_receipt": {
        "title": "Fee Receipt",
        "icon": "receipt",
        "form": ReceiptGenerateForm,
        "desc": "Official receipt for a recorded fee payment.",
    },
}


class DocumentDashboardView(EdFlowMixin, ListView):
    model = GeneratedDocument
    template_name = "documents/dashboard.html"
    context_object_name = "recent_documents"
    paginate_by = 15
    page_title = "Documents"
    page_subtitle = "ID cards, certificates, receipts (spec §23)"
    active_page = "documents"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["doc_meta"] = _DOC_META
        ctx["templates"] = DocumentTemplate.objects.filter(is_active=True)
        return ctx


class TemplateListView(EdFlowMixin, SearchMixin, ListView):
    model = DocumentTemplate
    template_name = "documents/template_list.html"
    context_object_name = "templates"
    paginate_by = 25
    page_title = "Document Templates"
    page_subtitle = "Configurable document bodies"
    active_page = "documents"
    search_fields = ["name", "doc_type"]
    search_placeholder = "Search templates…"


class TemplateCreateView(EdFlowMixin, CreateView):
    model = DocumentTemplate
    form_class = DocumentTemplateForm
    template_name = "documents/template_form.html"
    page_title = "New Template"
    page_subtitle = "Create a document template"
    active_page = "documents"

    def get_success_url(self):
        return reverse("documents:templates")

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(self.request, "documents", self.object.pk, "Created document template.")
        messages.success(self.request, "Template created.")
        return response


class TemplateUpdateView(EdFlowMixin, UpdateView):
    model = DocumentTemplate
    form_class = DocumentTemplateForm
    template_name = "documents/template_form.html"
    page_title = "Edit Template"
    page_subtitle = "Customize the document body"
    active_page = "documents"

    def get_success_url(self):
        return reverse("documents:templates")

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(self.request, "documents", self.object.pk, "Updated document template.")
        messages.success(self.request, "Template saved.")
        return response


class TemplateDeleteView(EdFlowMixin, DeleteView):
    model = DocumentTemplate
    template_name = "documents/confirm_delete.html"
    page_title = "Delete Template"
    active_page = "documents"

    def get_success_url(self):
        return reverse("documents:templates")

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.is_system:
            messages.error(request, "System templates cannot be deleted.")
            from django.shortcuts import redirect

            return redirect("documents:templates")
        super().post(request, *args, **kwargs)
        audit(request, "documents", obj.pk, "Deleted document template.")
        messages.success(request, "Template deleted.")
        from django.shortcuts import redirect

        return redirect("documents:templates")


class GenerateDocumentView(EdFlowMixin, FormView):
    """Renders and stores a document PDF for the given doc_type."""

    template_name = "documents/generate.html"
    active_page = "documents"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.doc_type = kwargs.get("doc_type", "")
        meta = _DOC_META.get(self.doc_type)
        if meta is None:
            raise Http404("Unknown document type.")
        self.meta = meta
        self.page_title = f"Generate — {meta['title']}"
        self.page_subtitle = meta["desc"]

    def get_form_class(self):
        return self.meta["form"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["meta"] = self.meta
        return ctx

    def _system_template(self):
        return DocumentTemplate.objects.filter(doc_type=self.doc_type).first()

    def _record(self, title, payload=None):
        return GeneratedDocument.objects.create(
            doc_type=self.doc_type,
            template=self._system_template(),
            student=payload.get("student") if payload else None,
            staff=payload.get("staff") if payload else None,
            title=title,
            generated_by=self.request.user,
        )

    def form_valid(self, form):
        student = form.cleaned_data.get("student")
        staff = form.cleaned_data.get("staff")
        template = self._system_template()

        if self.doc_type == "student_id_card":
            response = student_id_pdf(student)
            label = f"ID Card — {student.full_name} ({student.admission_number})"
        elif self.doc_type == "staff_id_card":
            response = staff_id_pdf(staff)
            label = f"Staff ID — {staff.employee_code}"
        elif self.doc_type == "admission_letter":
            response = admission_pdf(student, template)
            label = f"Admission letter — {student.full_name}"
        elif self.doc_type in ("bonafide_certificate", "character_certificate", "leaving_certificate"):
            purpose = form.cleaned_data.get("purpose") or ""
            extras = [f"Purpose: {purpose}"] if purpose else []
            response = certificate_pdf(student, template, extras)
            label = f"{self.meta['title']} — {student.full_name}"
        elif self.doc_type == "fee_receipt":
            payment = form.cleaned_data["payment"]
            response = fee_receipt_pdf(payment)
            label = f"Receipt {payment.receipt_number}"
        else:
            from django.shortcuts import redirect

            messages.error(self.request, "Unsupported document type.")
            return redirect("documents:list")

        record = self._record(label, {"student": student, "staff": staff})
        from django.core.files.base import ContentFile

        record.pdf.save(record.filename(), ContentFile(response.content))
        audit(self.request, "documents", record.pk, f"Generated {label}.")
        return response


class GeneratedListView(EdFlowMixin, SearchMixin, ListView):
    model = GeneratedDocument
    template_name = "documents/history.html"
    context_object_name = "documents"
    paginate_by = 25
    page_title = "Generated Documents"
    page_subtitle = "Recently generated PDFs"
    active_page = "documents"
    search_fields = ["title"]
    search_placeholder = "Search documents…"


class DocumentDeleteView(EdFlowMixin, DeleteView):
    model = GeneratedDocument
    template_name = "documents/confirm_delete.html"
    page_title = "Delete Document"
    active_page = "documents"

    def get_success_url(self):
        return reverse("documents:history")

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        super().post(request, *args, **kwargs)
        audit(request, "documents", obj.pk, "Deleted generated document.")
        messages.success(request, "Document deleted.")
        from django.shortcuts import redirect

        return redirect("documents:history")