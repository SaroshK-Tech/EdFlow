import datetime

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth
from django.views.generic import TemplateView

from apps.core.mixins import EdFlowMixin

from apps.fees.models import FeePayment, FeeVoucherItem


class ReportCenterView(EdFlowMixin, TemplateView):
    template_name = "reports/report_center.html"
    page_title = "Reports"
    page_subtitle = "One place for all school reports"
    active_page = "reports"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["report_cards"] = [
            {"key": "students", "title": "Students", "desc": "Enrollment by class and gender.",
             "icon": "people", "url": "reports:students"},
            {"key": "attendance", "title": "Attendance", "desc": "Present/absent breakdown per class for a date.",
             "icon": "calendar-check", "url": "reports:attendance"},
            {"key": "finance", "title": "Finance", "desc": "Collections, expenses and net position.",
             "icon": "graph-up-arrow", "url": "reports:finance"},
            {"key": "defaulters", "title": "Defaulters", "desc": "Students with outstanding fee balances.",
             "icon": "exclamation-triangle", "url": "reports:defaulters"},
        ]
        from apps.students.models import Student
        from apps.attendance.models import StudentAttendance
        from apps.staff.models import Staff

        ctx["quick_stats"] = {
            "students": Student.objects.count(),
            "staff": Staff.objects.count(),
            "attendance_today": StudentAttendance.objects.filter(
                date=datetime.date.today()
            ).count(),
            "payments": FeePayment.objects.count(),
        }
        return ctx


class StudentReportView(EdFlowMixin, TemplateView):
    template_name = "reports/student_report.html"
    page_title = "Student Report"
    page_subtitle = "Enrollment by class and gender"
    active_page = "reports"

    def get_context_data(self, **kwargs):
        from apps.students.models import Student

        ctx = super().get_context_data(**kwargs)
        qs = Student.objects.exclude(status="left")
        by_class = (
            qs.values("klass__name")
            .annotate(total=Count("id"))
            .order_by("klass__name")
        )
        by_gender = (
            qs.values("gender").annotate(total=Count("id")).order_by("-total")
        )
        ctx["by_class"] = list(by_class)
        ctx["by_gender"] = list(by_gender)
        ctx["total"] = qs.count()
        ctx["active"] = qs.filter(status="active").count()
        ctx["by_status"] = list(
            qs.values("status").annotate(total=Count("id")).order_by("-total")
        )
        return ctx


class AttendanceReportView(EdFlowMixin, TemplateView):
    template_name = "reports/attendance_report.html"
    page_title = "Attendance Report"
    page_subtitle = "Present / absent percentages per class"
    active_page = "reports"

    def get_context_data(self, **kwargs):
        from apps.attendance.models import AttendanceStatus, StudentAttendance

        ctx = super().get_context_data(**kwargs)
        date_str = self.request.GET.get("date", "")
        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            date = datetime.date.today()
        ctx["selected_date"] = date
        records = StudentAttendance.objects.filter(date=date)
        rows = list(
            records.values("student__klass__name", "status")
            .annotate(total=Count("id"))
            .order_by("student__klass__name")
        )
        summary = {}
        for row in rows:
            klass = row["student__klass__name"] or "Unassigned"
            bucket = summary.setdefault(
                klass, {"present": 0, "absent": 0, "late": 0, "leave": 0, "excused": 0, "total": 0}
            )
            bucket[row["status"]] = bucket.get(row["status"], 0) + row["total"]
            bucket["total"] += row["total"]
        for bucket in summary.values():
            bucket["present_percent"] = (
                round(bucket["present"] / bucket["total"] * 100, 1)
                if bucket["total"]
                else 0
            )
        ctx["summary"] = summary
        ctx["overall_present"] = records.filter(status=AttendanceStatus.PRESENT).count()
        ctx["overall_total"] = records.count()
        ctx["overall_percent"] = (
            round(ctx["overall_present"] / ctx["overall_total"] * 100, 1)
            if ctx["overall_total"]
            else 0
        )
        return ctx


class FinanceReportView(EdFlowMixin, TemplateView):
    template_name = "reports/finance_report.html"
    page_title = "Finance Report"
    page_subtitle = "Income, expenses and net position"
    active_page = "reports"

    def get_context_data(self, **kwargs):
        from apps.finance.views import _finance_summary
        from apps.finance.models import Expense

        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = _finance_summary()
        today = datetime.date.today()
        year_start = today.replace(month=1, day=1)
        income_by_month = list(
            FeePayment.objects.filter(paid_on__gte=year_start)
            .annotate(month=TruncMonth("paid_on"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        expenses_by_month = list(
            Expense.objects.filter(expense_date__gte=year_start)
            .annotate(month=TruncMonth("expense_date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        ctx["income_by_month"] = income_by_month
        ctx["expenses_by_month"] = expenses_by_month
        ctx["expense_by_category"] = list(
            Expense.objects.values("category__name")
            .annotate(total=Sum("amount"), n=Count("id"))
            .order_by("-total")
        )
        return ctx


class DefaultersReportView(EdFlowMixin, TemplateView):
    template_name = "reports/defaulters_report.html"
    page_title = "Defaulters"
    page_subtitle = "Students with outstanding fee balances"
    active_page = "reports"

    def get_context_data(self, **kwargs):
        from apps.students.models import Student
        from apps.fees.models import FeeVoucherItem

        ctx = super().get_context_data(**kwargs)
        students = Student.objects.exclude(status="left").select_related("klass")
        due_rows = (
            FeeVoucherItem.objects.filter(voucher__status="issued")
            .values("voucher__student_id")
            .annotate(due=Sum(F("amount") - F("discount")))
        )
        due_by_student = {row["voucher__student_id"]: row["due"] or 0 for row in due_rows}
        payments = (
            FeePayment.objects.values("student_id")
            .annotate(paid=Sum("amount"))
        )
        paid_by_student = {row["student_id"]: row["paid"] or 0 for row in payments}

        rows = []
        for student in students:
            due = due_by_student.get(student.pk, 0)
            paid = paid_by_student.get(student.pk, 0)
            balance = due - paid
            if balance > 0:
                rows.append(
                    {
                        "student": student,
                        "due": due,
                        "paid": paid,
                        "balance": balance,
                    }
                )
        rows.sort(key=lambda r: r["balance"], reverse=True)
        ctx["rows"] = rows[:200]
        ctx["total_outstanding"] = sum(r["balance"] for r in rows)
        ctx["student_count"] = len(rows)
        return ctx