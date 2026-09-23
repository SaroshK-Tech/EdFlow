import csv

from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import StudentForm, StudentImportForm
from .importers import HEADER_MAP, commit_import, parse_and_validate, serialize_rows
from .models import Student


def export_students_csv(request):
    """CSV export of all students (dashboard 'Export')."""
    students = Student.objects.select_related("klass", "section").order_by("admission_number")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="students.csv"'

    writer = csv.writer(response)
    writer.writerow(
        ["Admission No", "Registration No", "Roll No", "First Name", "Middle Name",
         "Last Name", "Gender", "Class", "Section", "Status", "Phone", "Email", "Address"]
    )
    for s in students:
        writer.writerow(
            [
                s.admission_number, s.registration_number or "", s.roll_number,
                s.first_name, s.middle_name, s.last_name, s.gender,
                s.klass.name if s.klass else "", s.section.name if s.section else "",
                s.get_status_display(), s.phone, s.email, s.address,
            ]
        )
    audit(request, "students.export_csv")
    return response


class StudentListView(EdFlowMixin, SearchMixin, ListView):
    model = Student
    template_name = "students/student_list.html"
    context_object_name = "students"
    paginate_by = 25
    page_title = "Students"
    page_subtitle = "360-degree profiles, search, filtering and documents"
    active_page = "students"
    search_fields = [
        "admission_number",
        "registration_number",
        "first_name",
        "middle_name",
        "last_name",
        "phone",
        "email",
    ]
    search_placeholder = "Search by name, admission no, phone…"


class StudentCreateView(EdFlowMixin, CreateView):
    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    page_title = "Add Student"
    active_page = "students"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"student.create {self.object.admission_number}")
        messages.success(self.request, f"Student {self.object.full_name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("students:detail", args=[self.object.pk])


class StudentUpdateView(EdFlowMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    context_object_name = "student"
    page_title = "Edit Student"
    active_page = "students"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"student.update {self.object.admission_number}")
        messages.success(self.request, "Student updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("students:detail", args=[self.object.pk])


class StudentDetailView(EdFlowMixin, DetailView):
    model = Student
    template_name = "students/student_detail.html"
    context_object_name = "student"
    active_page = "students"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.object.full_name
        ctx["page_subtitle"] = self.object.admission_number
        ctx["attendance"] = self.object.attendance.order_by("-date")[:12]
        ctx["payments"] = self.object.payments.order_by("-paid_on")[:10]
        ctx["guardians"] = self.object.guardians.all()
        return ctx


class StudentDeleteView(EdFlowMixin, DeleteView):
    model = Student
    template_name = "students/student_confirm_delete.html"
    context_object_name = "student"
    success_url = reverse_lazy("students:list")
    active_page = "students"

    def form_valid(self, form):
        audit(self.request, f"student.delete {self.object.admission_number}")
        messages.success(self.request, f"Student {self.object.full_name} deleted.")
        return super().form_valid(form)


class StudentImportView(EdFlowMixin, FormView):
    """Step 1: upload CSV, parse + validate offline, preview the result."""

    template_name = "students/student_import_form.html"
    form_class = StudentImportForm
    page_title = "Import Students"
    page_subtitle = "Upload a CSV of student records (parse, validate, preview)"
    active_page = "students"

    def form_valid(self, form):
        valid, errors, summary = parse_and_validate(form.files.get("csv_file"))
        self.request.session["student_import"] = {
            "rows": serialize_rows(valid, errors),
            "summary": summary,
            "skip_guardians": form.cleaned_data.get("skip_guardians", False),
        }
        if summary["valid"] == 0:
            messages.error(
                self.request,
                f"No valid rows in the file — {summary['error']} row(s) had errors.",
            )
            return super().form_valid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("students:import_preview")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["import_columns"] = list(HEADER_MAP.values())
        return ctx


class StudentImportPreviewView(EdFlowMixin, TemplateView):
    """Step 2: preview parsed rows, then commit the valid ones."""

    template_name = "students/student_import_preview.html"
    active_page = "students"

    def dispatch(self, request, *args, **kwargs):
        session = request.session.get("student_import")
        if not session:
            messages.info(request, "No import in progress — upload a CSV first.")
            return HttpResponseRedirect(reverse("students:import"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = self.request.session["student_import"]
        rows = session["rows"]
        ctx["summary"] = session["summary"]
        ctx["valid_rows"] = [r for r in rows if r["kind"] == "valid"]
        ctx["error_rows"] = [r for r in rows if r["kind"] == "error"]
        ctx["page_title"] = "Preview Import"
        ctx["page_subtitle"] = f"{ctx['summary']['valid']} valid, {ctx['summary']['error']} with errors"
        return ctx

    def post(self, request, *args, **kwargs):
        session = request.session.get("student_import")
        if not session:
            return HttpResponseRedirect(reverse("students:import"))
        valid_rows = [r for r in session["rows"] if r["kind"] == "valid"]
        result = commit_import(
            valid_rows,
            request=request,
            skip_guardians=session.get("skip_guardians", False),
        )
        audit(request, f"student.import_batch {result['created']} created")
        if result["created"]:
            messages.success(
                request,
                f"Imported {result['created']} student(s) and linked "
                f"{result['parents']} parent/guardian record(s).",
            )
        else:
            messages.error(request, "No rows were imported.")
        request.session.pop("student_import", None)
        return HttpResponseRedirect(reverse("students:list"))