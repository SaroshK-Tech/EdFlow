import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.staff.models import Staff
from apps.students.models import Status

from .forms import (
    DepartmentForm,
    DesignationForm,
    ExperienceForm,
    HRStaffForm,
    LeaveBalanceForm,
    LeaveRequestForm,
    QualificationForm,
)
from .models import (
    Department,
    Designation,
    Experience,
    LeaveBalance,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    Qualification,
)

try:
    from apps.attendance.models import StaffAttendance, StaffAttendanceStatus

    STAFF_ATTENDANCE_AVAILABLE = True
except ImportError:
    STAFF_ATTENDANCE_AVAILABLE = False

ATTENDANCE_STATUSES = [
    (value, label)
    for value, label in StaffAttendanceStatus.choices
    if value in ("present", "absent", "late", "leave")
]

DEFAULT_YEAR = datetime.date.today().year


def _parse_date(value):
    if value:
        try:
            return datetime.date.fromisoformat(value)
        except (TypeError, ValueError):
            pass
    return datetime.date.today()


class DepartmentCreateView(EdFlowMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    http_method_names = ["post"]
    template_name = "hr/department_form.html"
    page_title = "Add Department"
    active_page = "staff"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"department.create {self.object.name}")
        messages.success(self.request, f"Department {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("staff:list")


class DepartmentUpdateView(EdFlowMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department_form.html"
    context_object_name = "department"
    page_title = "Edit Department"
    active_page = "staff"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"department.update {self.object.name}")
        messages.success(self.request, "Department updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("staff:list")


class EmployeesView(EdFlowMixin, SearchMixin, ListView):
    """HR employee directory over staff.Staff with HR filters."""

    model = Staff
    template_name = "hr/employees.html"
    context_object_name = "employees"
    paginate_by = 25
    page_title = "Employees"
    page_subtitle = "HR directory — staff profiles, compensation and join dates"
    active_page = "hr"
    search_fields = [
        "employee_code",
        "first_name",
        "middle_name",
        "last_name",
        "designation",
        "email",
        "phone",
    ]
    search_placeholder = "Search employees…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("department")
        department = self.request.GET.get("department", "")
        designation = self.request.GET.get("designation", "")
        status = self.request.GET.get("status", "")
        if department.isdigit():
            qs = qs.filter(department_id=department)
        if designation:
            qs = qs.filter(designation=designation)
        if status in dict(Status.choices):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = Department.objects.all()
        ctx["designations"] = Designation.objects.all()
        ctx["status_choices"] = Status.choices
        ctx["current_department"] = self.request.GET.get("department", "")
        ctx["current_designation"] = self.request.GET.get("designation", "")
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["filter_params"] = {
            key: value
            for key, value in (
                ("department", ctx["current_department"]),
                ("designation", ctx["current_designation"]),
                ("status", ctx["current_status"]),
            )
            if value
        }
        return ctx


class EmployeeUpdateView(EdFlowMixin, UpdateView):
    model = Staff
    form_class = HRStaffForm
    template_name = "hr/employee_form.html"
    context_object_name = "employee"
    page_title = "Edit Employee"
    active_page = "hr"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"hr.staff.update {self.object.employee_code}")
        messages.success(self.request, f"{self.object.full_name} updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("hr:employees")


class EmployeeDetailView(EdFlowMixin, DetailView):
    """Full employee profile with qualifications and experience (spec §16)."""

    model = Staff
    template_name = "hr/employee_detail.html"
    context_object_name = "employee"
    active_page = "hr"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.object.full_name
        ctx["page_subtitle"] = f"{self.object.employee_code} · {self.object.designation or 'Staff'}"
        ctx["qualifications"] = self.object.qualifications.all()
        ctx["experiences"] = self.object.experiences.all()
        ctx["total_years"] = sum(e.years or 0 for e in ctx["experiences"])
        return ctx


class QualificationCreateView(EdFlowMixin, CreateView):
    model = Qualification
    form_class = QualificationForm
    template_name = "hr/qualification_form.html"
    page_title = "Add Qualification"
    active_page = "hr"

    def get_initial(self):
        initial = super().get_initial()
        staff_id = self.request.GET.get("staff")
        if staff_id and staff_id.isdigit():
            initial["staff"] = staff_id
        return initial

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"qualification.create {self.object.staff} {self.object.qualification}")
        messages.success(self.request, "Qualification added.")
        return resp

    def get_success_url(self):
        if self.object.staff_id:
            return reverse_lazy("hr:employee_detail", args=[self.object.staff_id])
        return reverse_lazy("hr:employees")


class QualificationUpdateView(EdFlowMixin, UpdateView):
    model = Qualification
    form_class = QualificationForm
    template_name = "hr/qualification_form.html"
    context_object_name = "qualification"
    page_title = "Edit Qualification"
    active_page = "hr"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"qualification.update {self.object.qualification}")
        messages.success(self.request, "Qualification updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("hr:employee_detail", args=[self.object.staff_id])


class QualificationDeleteView(EdFlowMixin, DeleteView):
    model = Qualification
    template_name = "hr/qualification_confirm_delete.html"
    context_object_name = "qualification"
    active_page = "hr"

    def get_success_url(self):
        return reverse_lazy("hr:employee_detail", args=[self.object.staff_id])

    def form_valid(self, form):
        audit(self.request, f"qualification.delete {self.object.qualification}")
        messages.success(self.request, "Qualification removed.")
        return super().form_valid(form)


class ExperienceCreateView(EdFlowMixin, CreateView):
    model = Experience
    form_class = ExperienceForm
    template_name = "hr/experience_form.html"
    page_title = "Add Experience"
    active_page = "hr"

    def get_initial(self):
        initial = super().get_initial()
        staff_id = self.request.GET.get("staff")
        if staff_id and staff_id.isdigit():
            initial["staff"] = staff_id
        return initial

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"experience.create {self.object.staff} {self.object.organisation}")
        messages.success(self.request, "Experience added.")
        return resp

    def get_success_url(self):
        if self.object.staff_id:
            return reverse_lazy("hr:employee_detail", args=[self.object.staff_id])
        return reverse_lazy("hr:employees")


class ExperienceUpdateView(EdFlowMixin, UpdateView):
    model = Experience
    form_class = ExperienceForm
    template_name = "hr/experience_form.html"
    context_object_name = "experience"
    page_title = "Edit Experience"
    active_page = "hr"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"experience.update {self.object.organisation}")
        messages.success(self.request, "Experience updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("hr:employee_detail", args=[self.object.staff_id])


class ExperienceDeleteView(EdFlowMixin, DeleteView):
    model = Experience
    template_name = "hr/experience_confirm_delete.html"
    context_object_name = "experience"
    active_page = "hr"

    def get_success_url(self):
        return reverse_lazy("hr:employee_detail", args=[self.object.staff_id])

    def form_valid(self, form):
        audit(self.request, f"experience.delete {self.object.organisation}")
        messages.success(self.request, "Experience removed.")
        return super().form_valid(form)


class DesignationListView(EdFlowMixin, SearchMixin, ListView):
    model = Designation
    template_name = "hr/designation_list.html"
    context_object_name = "designations"
    page_title = "Designations"
    page_subtitle = "Job titles, grades and departments"
    active_page = "hr"
    search_fields = ["name", "grade"]
    search_placeholder = "Search designations…"


class DesignationCreateView(EdFlowMixin, CreateView):
    model = Designation
    form_class = DesignationForm
    template_name = "hr/designation_form.html"
    page_title = "Add Designation"
    active_page = "hr"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"designation.create {self.object.name}")
        messages.success(self.request, f"Designation {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("hr:designations")


class DesignationUpdateView(EdFlowMixin, UpdateView):
    model = Designation
    form_class = DesignationForm
    template_name = "hr/designation_form.html"
    context_object_name = "designation"
    page_title = "Edit Designation"
    active_page = "hr"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"designation.update {self.object.name}")
        messages.success(self.request, "Designation updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("hr:designations")


class DesignationDeleteView(EdFlowMixin, DeleteView):
    model = Designation
    template_name = "hr/designation_confirm_delete.html"
    context_object_name = "designation"
    success_url = reverse_lazy("hr:designations")
    active_page = "hr"
    extra_context = {"heading": "Delete Designation", "cancel_url": "hr:designations"}

    def form_valid(self, form):
        audit(self.request, f"designation.delete {self.object.name}")
        messages.success(self.request, f"Designation {self.object.name} deleted.")
        return super().form_valid(form)


class LeaveListView(EdFlowMixin, SearchMixin, ListView):
    model = LeaveRequest
    template_name = "hr/leave_list.html"
    context_object_name = "leaves"
    paginate_by = 25
    page_title = "Leave Requests"
    page_subtitle = "Apply for and approve staff leave"
    active_page = "hr"
    search_fields = ["staff__employee_code", "staff__first_name", "staff__last_name"]
    search_placeholder = "Search by staff…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("staff", "leave_type", "reviewed_by")
        status = self.request.GET.get("status", "")
        if status in dict(LeaveStatus.choices):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = LeaveStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["filter_params"] = {"status": ctx["current_status"]} if ctx["current_status"] else {}
        return ctx


class LeaveCreateView(EdFlowMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "hr/leave_form.html"
    page_title = "Add Leave Request"
    active_page = "hr"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"leave.create {self.object.staff} {self.object.days}d")
        messages.success(self.request, f"Leave request created for {self.object.staff.full_name}.")
        return resp

    def get_success_url(self):
        return reverse_lazy("hr:leaves")


class LeaveUpdateView(EdFlowMixin, UpdateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "hr/leave_form.html"
    context_object_name = "leave"
    page_title = "Edit Leave Request"
    active_page = "hr"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Leave request updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("hr:leaves")


def leave_request_status(request, pk, action):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method != "POST":
        return redirect("hr:leaves")
    if action in (LeaveStatus.APPROVED, LeaveStatus.REJECTED) and leave.status == LeaveStatus.PENDING:
        leave.status = action
        leave.reviewed_by = request.user
        leave.reviewed_on = datetime.date.today()
        leave.save(update_fields=["status", "reviewed_by", "reviewed_on"])
        audit(request, f"leave.{action} {leave.pk} {leave.staff}")
        messages.success(
            request,
            f"{leave.staff.full_name}'s leave {leave.get_status_display().lower()}.",
        )
    else:
        messages.error(request, "Only pending requests can be reviewed.")
    return redirect("hr:leaves")


class LeaveBalancesView(EdFlowMixin, ListView):
    """Per-staff leave balances with inline editing and manual additions."""

    model = LeaveBalance
    template_name = "hr/leave_balances.html"
    context_object_name = "balances"
    active_page = "hr"

    def get_queryset(self):
        year = self._year()
        return LeaveBalance.objects.filter(year=year).select_related(
            "staff", "leave_type"
        )

    def _year(self):
        raw = self.request.POST.get("year") or self.request.GET.get("year") or ""
        try:
            return int(raw) if 2000 <= int(raw) <= 2100 else DEFAULT_YEAR
        except (TypeError, ValueError):
            return DEFAULT_YEAR

    def post(self, request, *args, **kwargs):
        if request.POST.get("balance_add"):
            self._add_balance(request)
        else:
            self._update_balances(request)
        return redirect(f"{request.path}?year={self._year()}")

    def _add_balance(self, request):
        try:
            staff_id = int(request.POST.get("staff", ""))
            leave_type_id = int(request.POST.get("leave_type", ""))
            year = int(request.POST.get("year", DEFAULT_YEAR))
            entitled = max(int(request.POST.get("entitled", 0)), 0)
            used = max(int(request.POST.get("used", 0)), 0)
            balance, created = LeaveBalance.objects.update_or_create(
                staff_id=staff_id,
                leave_type_id=leave_type_id,
                year=year,
                defaults={"entitled": entitled, "used": used},
            )
            audit(request, f"leavebalance.{'create' if created else 'update'} {balance}")
            messages.success(request, f"Leave balance saved for {balance.staff} ({year}).")
        except (ValueError, TypeError):
            messages.error(request, "Invalid values for the leave balance.")

    def _update_balances(self, request):
        saved = 0
        for key, value in request.POST.items():
            if not key.startswith("entitled_"):
                continue
            pk = int(key[len("entitled_"):])
            balance = LeaveBalance.objects.filter(pk=pk).first()
            if not balance:
                continue
            try:
                entitled = max(int(value), 0)
                used = max(int(request.POST.get(f"used_{pk}", balance.used)), 0)
            except (ValueError, TypeError):
                continue
            balance.entitled = entitled
            balance.used = used
            balance.save(update_fields=["entitled", "used"])
            saved += 1
        if saved:
            audit(request, f"leavebalance.bulk_update count={saved}")
            messages.success(request, f"Updated {saved} leave balance row(s).")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Leave Balances"
        ctx["page_subtitle"] = "Annual entitlements and usage per staff member"
        ctx["year"] = self._year()
        ctx["years"] = list(range(DEFAULT_YEAR - 2, DEFAULT_YEAR + 3))
        ctx["staff_members"] = Staff.objects.filter(status=Status.ACTIVE).order_by(
            "first_name", "last_name"
        )
        ctx["leave_types"] = LeaveType.objects.all()
        ctx["balance_form"] = LeaveBalanceForm()
        return ctx


class StaffAttendanceView(EdFlowMixin, TemplateView):
    """Daily staff register reusing attendance.StaffAttendance when present."""

    template_name = "hr/staff_attendance.html"
    page_title = "Staff Attendance"
    page_subtitle = "Daily staff register (present / absent / late / leave)"
    active_page = "hr"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["attendance_available"] = STAFF_ATTENDANCE_AVAILABLE
        ctx["date"] = _parse_date(self.request.GET.get("date"))
        ctx["statuses"] = ATTENDANCE_STATUSES
        rows = []
        if STAFF_ATTENDANCE_AVAILABLE:
            members = Staff.objects.filter(status=Status.ACTIVE).order_by(
                "first_name", "last_name"
            )
            records = {
                rec.staff_id: rec
                for rec in StaffAttendance.objects.filter(date=ctx["date"], staff__in=members)
            }
            rows = [{"staff": member, "record": records.get(member.pk)} for member in members]
        ctx["rows"] = rows
        return ctx

    def post(self, request):
        if not STAFF_ATTENDANCE_AVAILABLE:
            messages.error(request, "Staff attendance lives in the Attendance module.")
            return redirect("hr:staff_attendance")
        date = _parse_date(request.POST.get("date"))
        allowed = {value for value, _ in ATTENDANCE_STATUSES}
        saved = 0
        for key, value in request.POST.items():
            if not key.startswith("status_"):
                continue
            if value not in allowed:
                continue
            staff_id = int(key[len("status_"):])
            StaffAttendance.objects.update_or_create(
                staff_id=staff_id,
                date=date,
                defaults={"status": value, "marked_by": request.user},
            )
            saved += 1
        audit(request, f"hr.attendance.staff date={date} ({saved} staff)")
        messages.success(request, f"Staff attendance saved for {saved} staff on {date}.")
        return redirect(f"{request.path}?date={date}")