from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.hr.forms import DepartmentForm
from apps.hr.models import Department

from .forms import StaffDocumentForm, StaffForm
from .models import Staff, StaffDocument


class StaffListView(EdFlowMixin, SearchMixin, ListView):
    model = Staff
    template_name = "staff/staff_list.html"
    context_object_name = "staff_members"
    paginate_by = 25
    page_title = "Staff & HR"
    page_subtitle = "Teachers and non-teaching employees"
    active_page = "staff"
    search_fields = [
        "employee_code",
        "first_name",
        "middle_name",
        "last_name",
        "designation",
        "email",
        "phone",
    ]
    search_placeholder = "Search by name, code, designation…"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = Department.objects.prefetch_related("members")
        ctx["department_form"] = DepartmentForm()
        return ctx


class StaffDetailView(EdFlowMixin, DetailView):
    model = Staff
    template_name = "staff/staff_detail.html"
    context_object_name = "member"
    active_page = "staff"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        staff = self.object
        ctx["page_title"] = staff.full_name
        ctx["page_subtitle"] = f"{staff.employee_code} · {staff.designation or 'Staff'}"

        ctx["qualifications"] = staff.qualifications.all()
        ctx["experiences"] = staff.experiences.all()
        ctx["leave_balances"] = staff.leave_balances.select_related("leave_type")
        ctx["leave_requests"] = staff.leave_requests.select_related("leave_type")[:15]
        ctx["documents"] = staff.documents.all()
        ctx["payslips"] = staff.payslips.select_related("run")[:12]
        return ctx


class StaffCreateView(EdFlowMixin, CreateView):
    model = Staff
    form_class = StaffForm
    template_name = "staff/staff_form.html"
    page_title = "Add Staff Member"
    active_page = "staff"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"staff.create {self.object.employee_code}",
            object_type="Staff",
            object_id=self.object.pk,
        )
        messages.success(self.request, f"{self.object.full_name} added to staff.")
        return resp

    def get_success_url(self):
        return reverse("staff:detail", kwargs={"pk": self.object.pk})


class StaffUpdateView(EdFlowMixin, UpdateView):
    model = Staff
    form_class = StaffForm
    template_name = "staff/staff_form.html"
    context_object_name = "member"
    page_title = "Edit Staff Member"
    active_page = "staff"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Staff record updated.")
        return resp

    def get_success_url(self):
        return reverse("staff:detail", kwargs={"pk": self.object.pk})


class StaffDeleteView(EdFlowMixin, DeleteView):
    model = Staff
    template_name = "staff/staff_confirm_delete.html"
    context_object_name = "member"
    success_url = reverse_lazy("staff:list")
    active_page = "staff"

    def form_valid(self, form):
        messages.success(self.request, f"{self.object.full_name} removed from staff.")
        return super().form_valid(form)


class StaffDocumentCreateView(EdFlowMixin, CreateView):
    model = StaffDocument
    form_class = StaffDocumentForm
    template_name = "staff/staff_document_form.html"
    active_page = "staff"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs["pk"])
        ctx["member"] = staff
        ctx["page_title"] = f"Add Document — {staff.full_name}"
        return ctx

    def form_valid(self, form):
        form.instance.staff = get_object_or_404(Staff, pk=self.kwargs["pk"])
        form.instance.uploaded_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"staff.document {self.object.title}",
            object_type="StaffDocument",
            object_id=self.object.pk,
        )
        messages.success(self.request, "Document uploaded.")
        return resp

    def get_success_url(self):
        return reverse("staff:detail", kwargs={"pk": self.object.staff_id})


class StaffDocumentDeleteView(EdFlowMixin, DeleteView):
    model = StaffDocument
    template_name = "staff/staff_document_confirm_delete.html"
    active_page = "staff"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["member"] = self.object.staff
        ctx["page_title"] = f"Delete Document — {self.object.title}"
        return ctx

    def get_success_url(self):
        return reverse("staff:detail", kwargs={"pk": self.object.staff_id})


class StaffIdCardView(EdFlowMixin, TemplateView):
    """Printable staff ID card (spec §16 'Staff ID cards')."""

    template_name = "staff/staff_id_card.html"
    active_page = "staff"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["member"] = get_object_or_404(Staff, pk=self.kwargs["pk"])
        ctx["page_title"] = f"ID Card — {ctx['member'].full_name}"
        from apps.school.models import SchoolProfile

        ctx["school"] = SchoolProfile.objects.first()
        return ctx