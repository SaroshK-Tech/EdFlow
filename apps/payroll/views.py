import calendar
import datetime
import io
from itertools import chain

from django.contrib import messages
from django.db.models import Count, F, Sum, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import PayrollRunForm, SalaryComponentForm
from .models import PaySlip, PayrollRun, PayrollStatus, SalaryComponent
from .services import process_run


def _month_year(request):
    today = datetime.date.today()
    try:
        month = int(request.GET.get("month", today.month))
        year = int(request.GET.get("year", today.year))
    except (TypeError, ValueError):
        month, year = today.month, today.year
    month = month if 1 <= month <= 12 else today.month
    year = year if 2000 <= year <= 2100 else today.year
    return month, year


class PayrollRunListView(EdFlowMixin, SearchMixin, ListView):
    model = PayrollRun
    template_name = "payroll/run_list.html"
    context_object_name = "runs"
    paginate_by = 25
    page_title = "Payroll"
    page_subtitle = "Monthly payroll runs and pay slips"
    active_page = "payroll"
    search_fields = ["title", "status"]
    search_placeholder = "Search pay runs…"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["run_form"] = PayrollRunForm()
        ctx["today"] = datetime.date.today()
        return ctx


class PayrollRunCreateView(EdFlowMixin, FormView):
    """POST handler that creates and (unless draft) processes a run."""

    form_class = PayrollRunForm

    def form_valid(self, form):
        month = int(form.cleaned_data["month"])
        year = form.cleaned_data["year"]
        run, _ = PayrollRun.objects.get_or_create(
            month=month,
            year=year,
            defaults={"created_by": self.request.user},
        )
        if form.cleaned_data.get("draft"):
            run.status = PayrollStatus.DRAFT
            run.save(update_fields=["status"])
            audit(self.request, f"payroll.run.draft {run.period_label}")
            messages.success(self.request, f"Run {run.period_label} created as draft.")
        else:
            count = process_run(run)
            audit(self.request, f"payroll.run.process {run.period_label} slips={count}")
            messages.success(
                self.request, f"Run {run.period_label} processed — {count} pay slip(s)."
            )
        return redirect("payroll:detail", pk=run.pk)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid month or year for the payroll run.")
        return redirect("payroll:list")


class PayrollRunDetailView(EdFlowMixin, DetailView):
    model = PayrollRun
    template_name = "payroll/run_detail.html"
    context_object_name = "run"
    active_page = "payroll"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.object.period_label
        ctx["page_subtitle"] = f"Payroll run — {self.object.get_status_display()}"
        ctx["slips"] = self.object.slips.select_related("staff", "staff__department")
        ctx["totals"] = self.object.slips.aggregate(
            employees=Count("id", distinct=True),
            gross=Sum(F("basic") + F("allowances_total")),
            allowances=Sum("allowances_total"),
            deductions=Sum("deductions_total"),
            net=Sum("net"),
        )
        return ctx


class PayrollRunProcessView(EdFlowMixin, View):
    """Re-run processing (deletes + recreates slips; idempotent)."""

    def post(self, request, pk):
        run = get_object_or_404(PayrollRun, pk=pk)
        if run.status == PayrollStatus.PAID:
            messages.error(request, "This run is already marked paid.")
            return redirect("payroll:detail", pk=run.pk)
        count = process_run(run)
        audit(request, f"payroll.process {run.period_label} slips={count}")
        messages.success(
            request, f"Run {run.period_label} processed — {count} pay slip(s)."
        )
        return redirect("payroll:detail", pk=run.pk)


class PayrollRunPayView(EdFlowMixin, View):
    """Mark a processed run as paid."""

    def post(self, request, pk):
        run = get_object_or_404(PayrollRun, pk=pk)
        if run.status == PayrollStatus.DRAFT:
            messages.error(request, "Process the run before marking it paid.")
            return redirect("payroll:detail", pk=run.pk)
        run.status = PayrollStatus.PAID
        run.paid_on = datetime.date.today()
        run.save(update_fields=["status", "paid_on"])
        audit(request, f"payroll.pay {run.period_label}")
        messages.success(request, f"Run {run.period_label} marked as paid.")
        return redirect("payroll:detail", pk=run.pk)


class PaySlipView(EdFlowMixin, DetailView):
    model = PaySlip
    template_name = "payroll/slip.html"
    context_object_name = "slip"
    active_page = "payroll"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = f"Pay Slip — {self.object.staff.full_name}"
        ctx["page_subtitle"] = self.object.run.period_label
        return ctx


class PaySlipPdfView(EdFlowMixin, View):
    """ReportLab PDF of a pay slip, delivered inline for printing."""

    def get(self, request, pk):
        slip = get_object_or_404(PaySlip, pk=pk)
        staff = slip.staff

        from apps.school.models import SchoolProfile

        school = SchoolProfile.objects.first()
        school_name = school.name if school else "EdFlow School"
        school_address = school.address or ""
        phone_line = f" · {school.phone}" if school and school.phone else ""

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SchoolTitle", parent=styles["Title"], fontSize=16, spaceAfter=2
        )
        subtitle_style = ParagraphStyle(
            "SchoolAddr", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#555555")
        )
        h_style = ParagraphStyle(
            "SlipHead", parent=styles["Heading2"], fontSize=12, spaceBefore=6, spaceAfter=4
        )
        normal = styles["Normal"]
        small = ParagraphStyle(
            "Small", parent=normal, fontSize=8
        )

        story = []
        story.append(Paragraph(f"<b>{school_name}</b>", title_style))
        story.append(Paragraph(f"{school_address}{phone_line}", subtitle_style))
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                f"<b>PAY SLIP — {slip.run.period_label.upper()}</b>",
                h_style,
            )
        )
        story.append(Spacer(1, 4))

        info_rows = [
            ["Employee", staff.full_name, "Employee Code", staff.employee_code],
            [
                "Designation",
                staff.designation or "—",
                "Department",
                staff.department.name if staff.department else "—",
            ],
            ["Joining Date", staff.joining_date or "—", "Status", staff.get_status_display()],
        ]
        info_table = Table(
            [list(chain.from_iterable((Paragraph(f"<b>{label}</b>", small), Paragraph(str(value), small)) for label, value in zip(row[::2], row[1::2]))) for row in info_rows],
            colWidths=[30 * mm, 45 * mm, 40 * mm, 45 * mm],
        )
        info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f3f4")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 6))

        def amounts_table(header, rows):
            data = [[Paragraph(f"<b>{c}</b>", small) for c in header]]
            for row in rows:
                data.append([Paragraph(str(c), small) for c in row])
            table = Table(data, colWidths=[90 * mm, 55 * mm])
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaed")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            return table

        story.append(Paragraph("<b>Earnings</b>", h_style))
        earning_rows = [["Basic Salary", f"{slip.basic:.2f}"]]
        for item in slip.allowances:
            earning_rows.append([item["name"], item["amount"]])
        story.append(amounts_table(["Component", "Amount"], earning_rows))
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Deductions</b>", h_style))
        deduction_rows = [[item["name"], item["amount"]] for item in slip.deductions]
        if not deduction_rows:
            deduction_rows.append(["No deductions", "0.00"])
        story.append(amounts_table(["Component", "Amount"], deduction_rows))
        story.append(Spacer(1, 6))

        totals = [
            ["Total Allowances", f"{slip.allowances_total:.2f}"],
            ["Total Deductions", f"{slip.deductions_total:.2f}"],
            ["NET PAY", f"{slip.net:.2f}"],
        ]
        totals_data = []
        for i, (label, value) in enumerate(totals):
            if i == 2:
                net_style = ParagraphStyle(
                    "net", parent=small, fontSize=10, textColor=colors.white
                )
                totals_data.append(
                    [
                        Paragraph(f"<b>{label}</b>", net_style),
                        Paragraph(f"<b>{value}</b>", net_style),
                    ]
                )
            else:
                totals_data.append(
                    [Paragraph(f"<b>{label}</b>", small), Paragraph(f"<b>{value}</b>", small)]
                )
        totals_table = Table(totals_data, colWidths=[90 * mm, 55 * mm])
        totals_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#198754")),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(totals_table)
        story.append(Spacer(1, 10))
        story.append(
            Paragraph(
                f"Generated on {datetime.date.today():%d %b %Y} · EdFlow Payroll",
                subtitle_style,
            )
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )
        doc.build(story)
        buffer.seek(0)

        filename = f"payslip-{staff.employee_code}-{slip.run.month}{slip.run.year}.pdf"
        response = HttpResponse(buffer.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


class PayrollReportsView(EdFlowMixin, TemplateView):
    template_name = "payroll/reports.html"
    page_title = "Payroll Reports"
    page_subtitle = "Monthly totals and per-department breakdown"
    active_page = "payroll"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        month, year = _month_year(self.request)
        ctx["month"] = month
        ctx["year"] = year
        ctx["month_name"] = calendar.month_name[month]
        ctx["month_choices"] = [(m, calendar.month_name[m]) for m in range(1, 13)]
        today = datetime.date.today()
        ctx["year_choices"] = list(range(today.year - 2, today.year + 3))
        runs = PayrollRun.objects.filter(month=month, year=year)
        slips = PaySlip.objects.filter(run__in=runs).select_related("staff", "staff__department")
        ctx["run_count"] = runs.count()
        ctx["totals"] = slips.aggregate(
            employees=Count("staff", distinct=True),
            gross=Sum(F("basic") + F("allowances_total")),
            allowances=Sum("allowances_total"),
            deductions=Sum("deductions_total"),
            net=Sum("net"),
        )
        ctx["departments"] = list(
            slips.values("staff__department__name")
            .annotate(
                employees=Count("staff", distinct=True),
                gross=Sum(F("basic") + F("allowances_total")),
                allowances=Sum("allowances_total"),
                deductions=Sum("deductions_total"),
                net=Sum("net"),
            )
            .order_by("staff__department__name")
        )
        return ctx


# ---------------------------------------------------------------------------
# Salary components (allowances / deductions) management.
# ---------------------------------------------------------------------------


class ComponentListView(EdFlowMixin, SearchMixin, ListView):
    model = SalaryComponent
    template_name = "payroll/component_list.html"
    context_object_name = "components"
    page_title = "Salary Components"
    page_subtitle = "Allowances and deductions applied to every pay run"
    active_page = "payroll"
    search_fields = ["name"]
    search_placeholder = "Search components…"


class ComponentCreateView(EdFlowMixin, CreateView):
    model = SalaryComponent
    form_class = SalaryComponentForm
    template_name = "payroll/component_form.html"
    page_title = "Add Salary Component"
    page_subtitle = "Allowance or deduction (fixed amount or % of basic)"
    active_page = "payroll"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"payroll.component.create {self.object.name}",
            object_type="SalaryComponent",
            object_id=self.object.pk,
        )
        messages.success(self.request, f"Component '{self.object.name}' created.")
        return resp

    def get_success_url(self):
        return reverse("payroll:components")


class ComponentUpdateView(EdFlowMixin, UpdateView):
    model = SalaryComponent
    form_class = SalaryComponentForm
    template_name = "payroll/component_form.html"
    context_object_name = "component"
    page_title = "Edit Salary Component"
    active_page = "payroll"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Component updated.")
        return resp

    def get_success_url(self):
        return reverse("payroll:components")


class ComponentDeleteView(EdFlowMixin, DeleteView):
    model = SalaryComponent
    template_name = "payroll/component_confirm_delete.html"
    active_page = "payroll"

    def form_valid(self, form):
        messages.success(self.request, f"Component '{self.object.name}' deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("payroll:components")


class StaffPayslipsView(EdFlowMixin, ListView):
    """Pay-slip history for one staff member."""

    model = PaySlip
    template_name = "payroll/staff_payslips.html"
    context_object_name = "slips"
    active_page = "payroll"

    def get_queryset(self):
        from apps.staff.models import Staff

        self.staff = get_object_or_404(Staff, pk=self.kwargs["pk"])
        return PaySlip.objects.filter(staff=self.staff).select_related("run")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["staff"] = self.staff
        ctx["page_title"] = f"Pay Slips — {self.staff.full_name}"
        ctx["page_subtitle"] = self.staff.employee_code
        return ctx