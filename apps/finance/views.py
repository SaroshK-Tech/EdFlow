import csv
import datetime

from django.contrib import messages
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from openpyxl import Workbook

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.fees.models import FeeHead, FeePayment, FeeVoucher, PaymentMethod

from .forms import ExpenseCategoryForm, ExpenseForm, RefundForm
from .models import Expense, ExpenseCategory, Refund


def _finance_summary():
    """Aggregate income, expenses, outstanding and breakdowns for dashboards."""
    today = datetime.date.today()
    year_start = today.replace(month=1, day=1)

    income_all = (
        FeePayment.objects.aggregate(total=Sum("amount"))
    )["total"] or 0
    income_year = (
        FeePayment.objects.filter(paid_on__gte=year_start).aggregate(total=Sum("amount"))
    )["total"] or 0
    income_month = (
        FeePayment.objects.filter(paid_on__year=today.year, paid_on__month=today.month)
        .aggregate(total=Sum("amount"))
    )["total"] or 0

    expenses_all = Expense.objects.aggregate(total=Sum("amount"))["total"] or 0
    expenses_year = (
        Expense.objects.filter(expense_date__gte=year_start).aggregate(total=Sum("amount"))
    )["total"] or 0
    expenses_month = (
        Expense.objects.filter(expense_date__year=today.year, expense_date__month=today.month)
        .aggregate(total=Sum("amount"))
    )["total"] or 0

    refunds_all = Refund.objects.aggregate(total=Sum("amount"))["total"] or 0
    refunds_year = (
        Refund.objects.filter(refund_date__gte=year_start).aggregate(total=Sum("amount"))
    )["total"] or 0

    payments_by_method = list(
        FeePayment.objects.values("method")
        .annotate(total=Sum("amount"), n=Count("id"))
        .order_by("-total")
    )
    revenue_by_head = list(
        FeePayment.objects.values("fee_head__name")
        .annotate(total=Sum("amount"), n=Count("id"))
        .order_by("-total")[:12]
    )
    expenses_by_category = list(
        Expense.objects.values("category__name")
        .annotate(total=Sum("amount"), n=Count("id"))
        .order_by("-total")[:12]
    )

    # Outstanding per student: voucher total - payments.
    outstanding_rows = []
    defaulters = 0
    for voucher in (
        FeeVoucher.objects.filter(status="issued")
        .select_related("student")
        .order_by("-issued_on")
    ):
        paid = (
            FeePayment.objects.filter(student=voucher.student).aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )
        due = voucher.total - paid
        if due > 0:
            defaulters += 1
            overdue = voucher.due_date < today
            outstanding_rows.append(
                {
                    "student": voucher.student,
                    "due": due,
                    "due_date": voucher.due_date,
                    "overdue": overdue,
                }
            )
    outstanding_total = sum(row["due"] for row in outstanding_rows)
    outstanding_rows.sort(key=lambda r: r["due"], reverse=True)

    return {
        "income_all": income_all,
        "income_year": income_year,
        "income_month": income_month,
        "expenses_all": expenses_all,
        "expenses_year": expenses_year,
        "expenses_month": expenses_month,
        "refunds_all": refunds_all,
        "refunds_year": refunds_year,
        "net_year": income_year - expenses_year - refunds_year,
        "payments_by_method": payments_by_method,
        "revenue_by_head": revenue_by_head,
        "expenses_by_category": expenses_by_category,
        "outstanding_rows": outstanding_rows[:25],
        "outstanding_total": outstanding_total,
        "defaulters_count": defaulters,
        "payment_method_choices": PaymentMethod.choices,
    }


class FinanceDashboardView(EdFlowMixin, TemplateView):
    template_name = "finance/dashboard.html"
    page_title = "Fees & Finance"
    page_subtitle = "Income, expenses, outstanding fees and defaulters"
    active_page = "finance"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_finance_summary())
        return ctx


class ExpenseListView(EdFlowMixin, SearchMixin, ListView):
    model = Expense
    template_name = "finance/expense_list.html"
    context_object_name = "expenses"
    paginate_by = 25
    page_title = "Expenses"
    page_subtitle = "All school expenditure"
    active_page = "finance"
    search_fields = ["title", "payee", "invoice_number", "category__name", "notes"]

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("category")
            .order_by("-expense_date", "-id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_expenses"] = (
            self.request.user.is_authenticated
            and Expense.objects.aggregate(total=Sum("amount"))["total"]
            or 0
        )
        return ctx


class ExpenseCreateView(EdFlowMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expense_form.html"
    page_title = "Record Expense"
    page_subtitle = "Log an outgoing payment"
    active_page = "finance"

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"finance.expense {self.object.title} amount={self.object.amount}",
            object_type="Expense", object_id=self.object.pk,
        )
        messages.success(self.request, "Expense recorded.")
        return resp

    def get_success_url(self):
        return reverse_lazy("finance:expense_list")


class ExpenseUpdateView(EdFlowMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expense_form.html"
    page_title = "Edit Expense"
    active_page = "finance"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Expense updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("finance:expense_list")


class ExpenseDeleteView(EdFlowMixin, DeleteView):
    model = Expense
    template_name = "finance/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "expense"
        ctx["cancel_url"] = reverse("finance:expense_list")
        ctx["page_title"] = "Delete Expense"
        ctx["active_page"] = "finance"
        return ctx

    def form_valid(self, form):
        audit(self.request, f"finance.expense_delete {self.object.title}")
        messages.success(self.request, "Expense deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("finance:expense_list")


class ExpenseCategoryListView(EdFlowMixin, SearchMixin, ListView):
    model = ExpenseCategory
    template_name = "finance/category_list.html"
    context_object_name = "categories"
    page_title = "Expense Categories"
    active_page = "finance"
    search_fields = ["name", "description"]

    def get_queryset(self):
        return super().get_queryset().annotate(
            expense_count=Count("expenses"),
            expense_total=Sum("expenses__amount"),
        )


class ExpenseCategoryCreateView(EdFlowMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = "finance/category_form.html"
    page_title = "Add Expense Category"
    active_page = "finance"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Expense category created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("finance:category_list")


class ExpenseCategoryUpdateView(EdFlowMixin, UpdateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = "finance/category_form.html"
    page_title = "Edit Expense Category"
    active_page = "finance"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Expense category updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("finance:category_list")


class ExpenseCategoryDeleteView(EdFlowMixin, DeleteView):
    model = ExpenseCategory
    template_name = "finance/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "expense category"
        ctx["cancel_url"] = reverse("finance:category_list")
        ctx["page_title"] = "Delete Expense Category"
        ctx["active_page"] = "finance"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Expense category deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("finance:category_list")


class RefundListView(EdFlowMixin, SearchMixin, ListView):
    model = Refund
    template_name = "finance/refund_list.html"
    context_object_name = "refunds"
    paginate_by = 25
    page_title = "Refunds"
    page_subtitle = "Money returned to parents / students"
    active_page = "finance"
    search_fields = [
        "student__first_name", "student__last_name",
        "student__admission_number", "reason", "reference",
    ]

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("student")
            .order_by("-refund_date", "-id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_refunds"] = Refund.objects.aggregate(total=Sum("amount"))["total"] or 0
        return ctx


class RefundCreateView(EdFlowMixin, CreateView):
    model = Refund
    form_class = RefundForm
    template_name = "finance/refund_form.html"
    page_title = "Record Refund"
    page_subtitle = "Return money to a student / parent"
    active_page = "finance"

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"finance.refund {self.object.student} amount={self.object.amount}",
            object_type="Refund", object_id=self.object.pk,
        )
        messages.success(self.request, "Refund recorded.")
        return resp

    def get_success_url(self):
        return reverse_lazy("finance:refund_list")


class ReportsView(EdFlowMixin, TemplateView):
    template_name = "finance/reports.html"
    page_title = "Financial Reports"
    page_subtitle = "Revenue, expenses and net position"
    active_page = "finance"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_finance_summary())

        from django.db.models.functions import TruncMonth, TruncYear

        ctx["income_by_month"] = list(
            FeePayment.objects.annotate(month=TruncMonth("paid_on"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        ctx["expenses_by_month"] = list(
            Expense.objects.annotate(month=TruncMonth("expense_date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        ctx["recent_payments"] = (
            FeePayment.objects.select_related("student", "fee_head")
            .order_by("-paid_on", "-id")[:15]
        )
        ctx["recent_expenses"] = (
            Expense.objects.select_related("category").order_by("-expense_date", "-id")[:15]
        )
        return ctx


# ---------------------------------------------------------------------------
# Export helpers (Excel via openpyxl, CSV via stdlib) — spec §15 reports.
# ---------------------------------------------------------------------------


def _xlsx_response(filename, headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = filename.replace("-", " ")[:31]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    # Light header styling.
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)
    for column_cells in ws.columns:
        width = max(len(str(c.value or "")) for c in column_cells) + 2
        ws.column_dimensions[column_cells[0].column_letter].width = min(width, 40)
    buffer = __import__("io").BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([("" if v is None else str(v)) for v in row])
    return response


class ExpenseExportView(EdFlowMixin, View):
    def get(self, request, *args, **kwargs):
        qs = Expense.objects.select_related("category").order_by("-expense_date", "-id")
        headers = ["Date", "Title", "Category", "Amount", "Method", "Payee", "Invoice", "Notes"]
        rows = [
            [
                e.expense_date.isoformat(),
                e.title,
                e.category.name if e.category_id else "",
                str(e.amount),
                e.get_method_display(),
                e.payee,
                e.invoice_number,
                e.notes,
            ]
            for e in qs
        ]
        if request.GET.get("format") == "csv":
            return _csv_response("expenses", headers, rows)
        return _xlsx_response("expenses", headers, rows)


class RefundExportView(EdFlowMixin, View):
    def get(self, request, *args, **kwargs):
        qs = Refund.objects.select_related("student").order_by("-refund_date", "-id")
        headers = ["Date", "Student", "Amount", "Method", "Reason", "Reference", "Notes"]
        rows = [
            [
                r.refund_date.isoformat(),
                str(r.student),
                str(r.amount),
                r.get_method_display(),
                r.reason,
                r.reference,
                r.notes,
            ]
            for r in qs
        ]
        if request.GET.get("format") == "csv":
            return _csv_response("refunds", headers, rows)
        return _xlsx_response("refunds", headers, rows)


class CashflowExportView(EdFlowMixin, View):
    """Annual cash-flow statement export (spec §15 'Financial reports')."""

    def get(self, request, *args, **kwargs):
        from django.db.models.functions import TruncMonth

        today = datetime.date.today()
        year_start = today.replace(month=1, day=1)

        income = {
            str(r["month"])[:7]: r["total"]
            for r in FeePayment.objects.filter(paid_on__gte=year_start)
            .annotate(month=TruncMonth("paid_on"))
            .values("month")
            .annotate(total=Sum("amount"))
        }
        expenses = {
            str(r["month"])[:7]: r["total"]
            for r in Expense.objects.filter(expense_date__gte=year_start)
            .annotate(month=TruncMonth("expense_date"))
            .values("month")
            .annotate(total=Sum("amount"))
        }
        refunds = {
            str(r["month"])[:7]: r["total"]
            for r in Refund.objects.filter(refund_date__gte=year_start)
            .annotate(month=TruncMonth("refund_date"))
            .values("month")
            .annotate(total=Sum("amount"))
        }

        headers = ["Month", "Income", "Expenses", "Refunds", "Net"]
        rows = []
        for m in range(1, today.month + 1):
            key = f"{today.year:04d}-{m:02d}"
            inc = income.get(key, 0) or 0
            exp = expenses.get(key, 0) or 0
            ref = refunds.get(key, 0) or 0
            rows.append([key, inc, exp, ref, inc - exp - ref])

        if request.GET.get("format") == "csv":
            return _csv_response(f"cashflow-{today.year}", headers, rows)
        return _xlsx_response(f"cashflow-{today.year}", headers, rows)