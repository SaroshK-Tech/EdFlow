from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.shortcuts import redirect

from apps.core.logging import audit

from .forms import (
    AcademicYearForm,
    HolidayForm,
    SchoolProfileForm,
    TermForm,
    WorkingDayForm,
)
from .models import (
    AcademicYear,
    Holiday,
    SchoolProfile,
    Term,
    WorkingDay,
)


def _require_admin(user):
    if not user.is_authenticated:
        return False
    role = getattr(user, "role", None)
    return (
        user.is_superuser
        or user.is_staff
        or (role and role.key in {
            "super_admin",
            "school_administrator",
            "principal",
        })
    )


class _SchoolAdminMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not _require_admin(request.user):
            messages.error(
                request, "You do not have permission to manage school settings."
            )
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)


class SchoolProfileView(_SchoolAdminMixin, UpdateView):
    """Single-row school profile editor (spec §3)."""

    model = SchoolProfile
    form_class = SchoolProfileForm
    template_name = "school/settings.html"
    context_object_name = "profile"
    page_title = "School Settings"
    page_subtitle = "Institution identity and contact details"

    def get_object(self, queryset=None):
        return SchoolProfile.objects.first()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            {
                "academic_years": AcademicYear.objects.all(),
                "terms": Term.objects.select_related("academic_year").all(),
                "working_days": WorkingDay.objects.select_related(
                    "academic_year"
                ).all(),
                "holidays": Holiday.objects.select_related("academic_year").all(),
            }
        )
        return ctx

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"school.profile.update {self.object.name}")
        messages.success(self.request, "School profile updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class AcademicYearCreateView(_SchoolAdminMixin, CreateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name = "school/form.html"
    page_title = "Add Academic Year"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"academic_year.create {self.object.name}")
        messages.success(self.request, f"Academic year {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class AcademicYearUpdateView(_SchoolAdminMixin, UpdateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name = "school/form.html"
    context_object_name = "academic_year"
    page_title = "Edit Academic Year"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Academic year updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class TermCreateView(_SchoolAdminMixin, CreateView):
    model = Term
    form_class = TermForm
    template_name = "school/form.html"
    page_title = "Add Term"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"term.create {self.object}")
        messages.success(self.request, "Term added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class TermUpdateView(_SchoolAdminMixin, UpdateView):
    model = Term
    form_class = TermForm
    template_name = "school/form.html"
    context_object_name = "term"
    page_title = "Edit Term"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Term updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class WorkingDayCreateView(_SchoolAdminMixin, CreateView):
    model = WorkingDay
    form_class = WorkingDayForm
    template_name = "school/form.html"
    page_title = "Add Working Day"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"working_day.create {self.object}")
        messages.success(self.request, "Working day added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class WorkingDayDeleteView(_SchoolAdminMixin, DeleteView):
    model = WorkingDay
    template_name = "school/confirm_delete.html"
    context_object_name = "working_day"

    def form_valid(self, form):
        audit(self.request, f"working_day.delete {self.object}")
        messages.success(self.request, "Working day removed.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("school:settings")


class HolidayCreateView(_SchoolAdminMixin, CreateView):
    model = Holiday
    form_class = HolidayForm
    template_name = "school/form.html"
    page_title = "Add Holiday"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"holiday.create {self.object.name}")
        messages.success(self.request, "Holiday added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class HolidayUpdateView(_SchoolAdminMixin, UpdateView):
    model = Holiday
    form_class = HolidayForm
    template_name = "school/form.html"
    context_object_name = "holiday"
    page_title = "Edit Holiday"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Holiday updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("school:settings")


class HolidayDeleteView(_SchoolAdminMixin, DeleteView):
    model = Holiday
    template_name = "school/confirm_delete.html"
    context_object_name = "holiday"

    def form_valid(self, form):
        audit(self.request, f"holiday.delete {self.object.name}")
        messages.success(self.request, "Holiday deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("school:settings")