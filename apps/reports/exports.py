"""Excel (openpyxl) and PDF (ReportLab) exports for the reports centre.

All rendering is local and offline-first (spec §19/§23). Every exporter
mirrors the data shown on the corresponding on-screen report so the numbers
always agree.
"""

import datetime
import io

from django.db.models import Count, F, Sum
from django.http import HttpResponse

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
TOTAL_FONT = Font(bold=True)
AMOUNT_FMT = '#,##0.00'


def _response(buffer, filename, content_type, inline=True):
    disposition = "inline" if inline else "attachment"
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type=content_type)
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


def _style_sheet(wb, ws, rows, start_row=1, money_cols=()):
    """Style an Excel table as a clean report sheet."""
    from openpyxl.cell.cell import Cell

    for cell in ws[start_row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows:
        for cell in row:
            cell.border = cell.border
    widths = {}
    for row in ws.iter_rows(min_row=start_row, max_row=ws.max_row):
        for cell in row:
            name = cell.column_letter
            value = "" if cell.value is None else str(cell.value)
            widths[name] = max(widths.get(name, 0), min(len(value) * 2, 40))
            if isinstance(cell.value, (int, float)):
                if name in money_cols:
                    cell.number_format = AMOUNT_FMT
                cell.alignment = Alignment(horizontal="right")
    for name, width in widths.items():
        ws.column_dimensions[name].width = max(width, 10)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)


def _excel_report(ws, title, subtitle, headers, data_rows, money_columns=()):
    """Write a title block + a headed table into ``ws``."""
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = subtitle
    ws["A2"].font = Font(size=10, italic=True, color="666666")
    header_row = 4
    ws.append([" "] + headers)  # dummy to keep append() aligned with data rows
    for cell in ws[header_row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for data in data_rows:
        ws.append(data)
    last = ws.max_row
    money = {get_column_letter(i + 2) for i in range(len(headers)) if i in money_columns}
    for row in ws.iter_rows(min_row=header_row + 1, max_row=last):
        for cell in row:
            name = cell.column_letter
            if name in money and isinstance(cell.value, (int, float)):
                cell.number_format = AMOUNT_FMT
                cell.alignment = Alignment(horizontal="right")
    widths = {}
    for row in ws.iter_rows(min_row=header_row, max_row=last):
        for cell in row:
            name = cell.column_letter
            value = "" if cell.value is None else str(cell.value)
            widths[name] = max(widths.get(name, 0), min(len(value) * 2, 45))
    for name, width in widths.items():
        ws.column_dimensions[name].width = max(width, 11)
    if ws.max_row >= header_row + 1:
        ws.freeze_panes = ws.cell(row=header_row + 1, column=2)


def students_xlsx(request):
    from apps.students.models import Student

    qs = Student.objects.select_related("klass", "section").order_by("admission_number")
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    _excel_report(
        ws,
        "Student Directory",
        f"Generated {datetime.date.today():%d %b %Y} · {qs.count()} students (excl. left)",
        ["Admission No", "Registration No", "Roll No", "First", "Middle", "Last",
         "Gender", "Class", "Section", "Status", "Phone", "Email", "Address", "Joined"],
        [
            [
                s.admission_number, s.registration_number or "", s.roll_number,
                s.first_name, s.middle_name or "", s.last_name, s.gender,
                s.klass.name if s.klass else "", s.section.name if s.section else "",
                s.get_status_display(), s.phone, s.email, s.address,
                s.joined_at.strftime("%d %b %Y") if s.joined_at else "",
            ]
            for s in qs.exclude(status="left")
        ],
    )
    buffer = io.BytesIO()
    wb.save(buffer)
    from apps.core.logging import audit

    audit(request, "reports.students_xlsx")
    return _response(buffer, "students-report.xlsx", XLSX_MIME, inline=False)


def attendance_xlsx(request):
    from apps.attendance.models import AttendanceStatus, StudentAttendance

    date_str = request.GET.get("date", "")
    try:
        date = datetime.date.fromisoformat(date_str)
    except ValueError:
        date = datetime.date.today()
    records = StudentAttendance.objects.filter(date=date)
    rows = list(
        records.values("student__klass__name", "status")
        .annotate(total=Count("id"))
        .order_by("student__klass__name")
    )
    summary = {}
    for row in rows:
        klass = row["student__klass__name"] or "Unassigned"
        bucket = summary.setdefault(klass, {"present": 0, "absent": 0, "late": 0, "leave": 0, "excused": 0, "total": 0})
        bucket[row["status"]] = bucket.get(row["status"], 0) + row["total"]
        bucket["total"] += row["total"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    ws["A1"] = "Attendance Summary"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Date: {date:%d %b %Y}"
    ws["A2"].font = Font(size=10, italic=True, color="666666")
    header_row = 4
    headers = ["Class", "Present", "Absent", "Late", "Leave", "Excused", "Marked", "Rate %"]
    ws.append([" "] + headers)
    for cell in ws[header_row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    for klass, b in summary.items():
        ws.append([klass, b["present"], b["absent"], b["late"], b["leave"], b["excused"], b["total"],
                   round(b["present"] / b["total"] * 100, 1) if b["total"] else 0])
    last = ws.max_row
    widths = {}
    for row in ws.iter_rows(min_row=header_row, max_row=last):
        for cell in row:
            name = cell.column_letter
            value = "" if cell.value is None else str(cell.value)
            widths[name] = max(widths.get(name, 0), min(len(value) * 2, 40))
    for name, width in widths.items():
        ws.column_dimensions[name].width = max(width, 11)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=2)
    buffer = io.BytesIO()
    wb.save(buffer)
    from apps.core.logging import audit

    audit(request, f"reports.attendance_xlsx {date}")
    return _response(buffer, f"attendance-{date}.xlsx", XLSX_MIME, inline=False)


def finance_xlsx(request):
    from apps.finance.views import _finance_summary
    from apps.fees.models import FeePayment

    summary = _finance_summary()
    wb = Workbook()
    ws = wb.active
    ws.title = "Finance"
    ws["A1"] = "Finance Report"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Generated {datetime.date.today():%d %b %Y}"
    ws["A2"].font = Font(size=10, italic=True, color="666666")

    ws["A4"] = "Summary"
    ws["A4"].font = Font(bold=True, size=12)
    summary_rows = [
        ["Collections (YTD)", summary["income_year"]],
        ["Expenses (YTD)", summary["expenses_year"]],
        ["Refunds (YTD)", summary["refunds_year"]],
        ["Net (YTD)", summary["net_year"]],
    ]
    for label, value in summary_rows:
        ws.append([label, value])
    ws.append([])

    ws.append([" ", "Income by head"])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    for row_ in summary["revenue_by_head"]:
        ws.append(["  ", row_["fee_head__name"] or "—", row_["total"], row_["n"]])
    ws.append([])

    ws.append([" ", "Expenses by category"])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    for row_ in summary["expenses_by_category"]:
        ws.append(["  ", row_["category__name"] or "—", row_["total"], row_["n"]])

    for row in ws.iter_rows(min_row=5):
        for cell in row:
            if isinstance(cell.value, (int, float)):
                cell.number_format = AMOUNT_FMT
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 8
    buffer = io.BytesIO()
    wb.save(buffer)
    from apps.core.logging import audit

    audit(request, "reports.finance_xlsx")
    return _response(buffer, "finance-report.xlsx", XLSX_MIME, inline=False)


def defaulters_xlsx(request):
    rows = _defaulters_rows()
    wb = Workbook()
    ws = wb.active
    ws.title = "Defaulters"
    _excel_report(
        ws,
        "Fee Defaulters",
        f"Generated {datetime.date.today():%d %b %Y} · {len(rows)} students owing",
        ["Admission No", "Student", "Class", "Demanded", "Paid", "Balance"],
        [[r["student"].admission_number, r["student"].full_name,
          r["student"].klass.name if r["student"].klass else "",
          r["due"], r["paid"], r["balance"]] for r in rows],
        money_columns=(3, 4, 5),
    )
    buffer = io.BytesIO()
    wb.save(buffer)
    from apps.core.logging import audit

    audit(request, "reports.defaulters_xlsx")
    return _response(buffer, "fee-defaulters.xlsx", XLSX_MIME, inline=False)


def _defaulters_rows():
    from apps.fees.models import FeePayment, FeeVoucherItem
    from apps.students.models import Student

    rows = []
    students = Student.objects.exclude(status="left").select_related("klass")
    due_rows = (
        FeeVoucherItem.objects.filter(voucher__status="issued")
        .values("voucher__student_id")
        .annotate(due=Sum(F("amount") - F("discount")))
    )
    due_by_student = {row["voucher__student_id"]: row["due"] or 0 for row in due_rows}
    paid_by_student = {
        row["student_id"]: row["paid"] or 0
        for row in FeePayment.objects.values("student_id").annotate(paid=Sum("amount"))
    }
    for student in students:
        due = due_by_student.get(student.pk, 0)
        paid = paid_by_student.get(student.pk, 0)
        balance = due - paid
        if balance > 0:
            rows.append({"student": student, "due": due, "paid": paid, "balance": balance})
    rows.sort(key=lambda r: r["balance"], reverse=True)
    return rows[:200]


def _report_pdf(title, subtitle, headers, data_rows, filename, money_columns=()):
    """Generic landscape table PDF (ReportLab platypus)."""
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontSize = 8
    title_style = styles["Title"]
    sub_style = styles["Italic"]

    story = [
        Paragraph(title, title_style),
        Paragraph(subtitle, sub_style),
        Spacer(1, 6),
    ]
    table_data = [[Paragraph(f"<b>{h}</b>", normal) for h in headers]]
    for data in data_rows:
        table_data.append([Paragraph(str(v), normal) for v in data])

    col_count = len(headers)
    usable = A4[0] - 36 * mm
    col_widths = [usable / col_count] * col_count
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7FB")]),
    ]
    for i in money_columns:
        style_cmds.append(("ALIGN", (i, 1), (i, -1), "RIGHT"))
    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Generated {datetime.date.today():%d %b %Y} · EdFlow", sub_style))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title=title,
    )
    doc.build(story)
    from apps.core.logging import audit

    return _response(buffer, filename, "application/pdf", inline=False)


def students_pdf(request):
    from apps.students.models import Student

    qs = list(Student.objects.select_related("klass", "section").exclude(status="left").order_by("admission_number"))
    from apps.core.logging import audit

    audit(request, "reports.students_pdf")
    return _report_pdf(
        "Student Directory",
        f"{len(qs)} students",
        ["Admission No", "Name", "Gender", "Class", "Section", "Status", "Phone", "Joined"],
        [
            [s.admission_number, s.full_name, s.gender,
             s.klass.name if s.klass else "", s.section.name if s.section else "",
             s.get_status_display(), s.phone,
             s.joined_at.strftime("%d %b %Y") if s.joined_at else ""]
            for s in qs
        ],
        "students-report.pdf",
    )


def attendance_pdf(request):
    from apps.attendance.models import StudentAttendance

    date_str = request.GET.get("date", "")
    try:
        date = datetime.date.fromisoformat(date_str)
    except ValueError:
        date = datetime.date.today()
    records = StudentAttendance.objects.filter(date=date)
    rows = list(
        records.values("student__klass__name", "status")
        .annotate(total=Count("id"))
        .order_by("student__klass__name")
    )
    summary = {}
    for row in rows:
        klass = row["student__klass__name"] or "Unassigned"
        bucket = summary.setdefault(klass, {"present": 0, "absent": 0, "late": 0, "leave": 0, "excused": 0, "total": 0})
        bucket[row["status"]] = bucket.get(row["status"], 0) + row["total"]
        bucket["total"] += row["total"]
    from apps.core.logging import audit

    audit(request, f"reports.attendance_pdf {date}")
    return _report_pdf(
        "Attendance Summary",
        f"Date: {date:%d %b %Y}",
        ["Class", "Present", "Absent", "Late", "Leave", "Excused", "Marked", "Rate %"],
        [[klass, b["present"], b["absent"], b["late"], b["leave"], b["excused"], b["total"],
          f'{round(b["present"] / b["total"] * 100, 1) if b["total"] else 0}%']
         for klass, b in summary.items()],
        f"attendance-{date}.pdf",
    )


def finance_pdf(request):
    from apps.finance.views import _finance_summary

    summary = _finance_summary()
    from apps.core.logging import audit

    audit(request, "reports.finance_pdf")
    return _report_pdf(
        "Finance Report",
        "Collections, expenses and net position",
        ["Metric", "Amount"],
        [
            ["Collections (YTD)", summary["income_year"]],
            ["Expenses (YTD)", summary["expenses_year"]],
            ["Refunds (YTD)", summary["refunds_year"]],
            ["Net (YTD)", summary["net_year"]],
        ],
        "finance-report.pdf",
        money_columns=(1,),
    )


def defaulters_pdf(request):
    rows = _defaulters_rows()
    from apps.core.logging import audit

    audit(request, "reports.defaulters_pdf")
    return _report_pdf(
        "Fee Defaulters",
        f"{len(rows)} students with outstanding balances",
        ["Admission No", "Student", "Class", "Demanded", "Paid", "Balance"],
        [
            [r["student"].admission_number, r["student"].full_name,
             r["student"].klass.name if r["student"].klass else "",
             r["due"], r["paid"], r["balance"]]
            for r in rows
        ],
        "fee-defaulters.pdf",
        money_columns=(3, 4, 5),
    )