import calendar
import csv
import datetime
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.academics.models import Class, Period, Section
from apps.core.logging import audit
from apps.core.realtime import broadcast
from apps.staff.models import Staff
from apps.students.models import Status, Student
from apps.timetable.models import TimetableEntry, TimetableStatus

from .forms import AttendanceSelectorForm
from .models import (
    AttendanceStatus,
    PeriodAttendance,
    StaffAttendance,
    StaffAttendanceStatus,
    StudentAttendance,
)
from .services import enqueue_absence_messages

STATUS_FIELD_PREFIX = "status_"


def _parse_date(value):
    if value:
        try:
            return datetime.date.fromisoformat(value)
        except (TypeError, ValueError):
            pass
    return datetime.date.today()


def _parse_time(value):
    if value:
        try:
            return datetime.time.fromisoformat(value)
        except (TypeError, ValueError):
            return None
    return None


def _int_or(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _class_students(klass, section=None):
    students = Student.objects.filter(klass=klass, status=Status.ACTIVE)
    if section:
        students = students.filter(section=section)
    return students.order_by("roll_number", "first_name")


def _periods_for(klass, date, section=None):
    """Published timetable periods for the weekday, else all school periods."""

    weekday = str(date.isoweekday())
    entries = (
        TimetableEntry.objects.filter(
            timetable__status=TimetableStatus.PUBLISHED,
            weekday=weekday,
            klass=klass,
        )
        .select_related("period", "subject")
        .order_by("period__order")
    )
    if section:
        entries = entries.filter(section=section)
    period_map = {}
    for entry in entries:
        if entry.period.is_break:
            continue
        period_map.setdefault(
            entry.period_id, {"period": entry.period, "subject": entry.subject}
        )
    if period_map:
        return period_map
    periods = Period.objects.filter(is_break=False).order_by("order")
    return {p.pk: {"period": p, "subject": None} for p in periods}


def _notify_absent(absent_ids, period_info=None):
    if not absent_ids:
        return
    for student in Student.objects.filter(pk__in=absent_ids):
        enqueue_absence_messages(student, period_info=period_info)


@login_required
def mark_attendance(request):
    """Two-step register: pick date/class/section, then save the roster."""

    students = Student.objects.none()

    if request.method == "POST":
        form = AttendanceSelectorForm(request.POST)
        date = request.POST.get("date") or datetime.date.today()
        klass_id = request.POST.get("klass")
        section_id = request.POST.get("section") or None
        saved = 0
        absent_ids = set()
        for key, value in request.POST.items():
            if not key.startswith(STATUS_FIELD_PREFIX):
                continue
            if value not in AttendanceStatus.values:
                continue
            student_id = int(key[len(STATUS_FIELD_PREFIX):])
            StudentAttendance.objects.update_or_create(
                student_id=student_id,
                date=date,
                period=None,
                defaults={
                    "status": value,
                    "recorded_by": request.user,
                    "remarks": request.POST.get(f"remark_{student_id}", ""),
                },
            )
            if value == AttendanceStatus.ABSENT:
                absent_ids.add(student_id)
            saved += 1
        _notify_absent(absent_ids)
        broadcast("attendance.updated", {"class": klass_id, "date": str(date), "saved": saved})
        audit(
            request,
            f"attendance.mark class={klass_id} date={date} ({saved} students)",
        )
        messages.success(request, f"Attendance saved for {saved} students on {date}.")
        return redirect("attendance:list")

    # GET: selector form; show roster when a class is chosen.
    form = AttendanceSelectorForm(request.GET or None)
    if form.is_valid():
        klass = form.cleaned_data["klass"]
        section = form.cleaned_data["section"]
        students = Student.objects.filter(klass=klass, status=Status.ACTIVE)
        if section:
            students = students.filter(section=section)
        students = students.order_by("roll_number")

    return render(
        request,
        "attendance/mark.html",
        {
            "form": form,
            "students": students,
            "statuses": AttendanceStatus.choices,
            "page_title": "Mark Attendance",
            "page_subtitle": "Select a class to take the register",
            "active_page": "attendance",
        },
    )


@login_required
def attendance_list(request):
    date = request.GET.get("date") or datetime.date.today()
    records = (
        StudentAttendance.objects.filter(date=date)
        .select_related("student__klass", "student__section")
        .order_by("student__roll_number")
    )
    breakdown = list(
        records.values("status").annotate(count=Count("id")).order_by("status")
    )
    return render(
        request,
        "attendance/list.html",
        {
            "date": date,
            "records": records,
            "breakdown": breakdown,
            "page_title": "Attendance",
            "page_subtitle": f"Daily register for {date}",
            "active_page": "attendance",
        },
    )


@login_required
def period_attendance(request):
    """Period × student grid, saved in bulk as PeriodAttendance rows."""

    if request.method == "POST":
        date = _parse_date(request.POST.get("date"))
        klass_id = request.POST.get("klass")
        section_id = request.POST.get("section") or None
        klass = Class.objects.filter(pk=klass_id).first() if str(klass_id).isdigit() else None
        if not klass:
            messages.error(request, "Select a class before saving period attendance.")
            return redirect("attendance:period")
        section = Section.objects.filter(pk=section_id).first() if str(section_id).isdigit() else None
        period_map = _periods_for(klass, date, section)
        saved = 0
        absent = {}
        for period_id, info in period_map.items():
            prefix = f"status_{period_id}_"
            for key, value in request.POST.items():
                if not key.startswith(prefix):
                    continue
                if value not in AttendanceStatus.values:
                    continue
                student_id = int(key[len(prefix):])
                PeriodAttendance.objects.update_or_create(
                    student_id=student_id,
                    date=date,
                    period_id=period_id,
                    defaults={
                        "status": value,
                        "subject": info["subject"],
                        "klass": klass,
                        "marked_by": request.user,
                    },
                )
                if value == AttendanceStatus.ABSENT:
                    absent.setdefault(student_id, info["period"])
                saved += 1
        for student_id, period in absent.items():
            _notify_absent([student_id], period_info=str(period))
        audit(
            request,
            f"attendance.period class={klass} date={date} ({saved} marks)",
        )
        messages.success(request, f"Period attendance saved for {saved} marks on {date}.")
        return redirect(f"{request.path}?date={date}&klass={klass.pk}")

    date = _parse_date(request.GET.get("date"))
    klass_id = request.GET.get("klass") or ""
    section_id = request.GET.get("section") or ""
    klass = Class.objects.filter(pk=klass_id).first() if klass_id.isdigit() else None
    section = Section.objects.filter(pk=section_id).first() if section_id.isdigit() else None

    rows = []
    students = []
    if klass:
        period_map = _periods_for(klass, date, section)
        students = list(_class_students(klass, section))
        period_ids = list(period_map.keys())
        existing = PeriodAttendance.objects.filter(
            date=date, student__in=students, period_id__in=period_ids
        )
        grid = {(rec.student_id, rec.period_id): rec.status for rec in existing}
        for info in period_map.values():
            period = info["period"]
            cells = [
                {
                    "student": student,
                    "status": grid.get((student.pk, period.pk), ""),
                }
                for student in students
            ]
            rows.append({"period": period, "subject": info["subject"], "cells": cells})

    return render(
        request,
        "attendance/period.html",
        {
            "date": date,
            "klass": klass,
            "section": section,
            "klasses": Class.objects.all(),
            "sections": Section.objects.select_related("klass"),
            "rows": rows,
            "students": students,
            "statuses": AttendanceStatus.choices,
            "page_title": "Period Attendance",
            "page_subtitle": "Subject-wise register from the published timetable",
            "active_page": "attendance",
        },
    )


@login_required
def staff_attendance(request):
    """Daily staff register with check-in/out and overtime."""

    if request.method == "POST":
        date = _parse_date(request.POST.get("date"))
        saved = 0
        for key, value in request.POST.items():
            if not key.startswith(STATUS_FIELD_PREFIX):
                continue
            if value not in StaffAttendanceStatus.values:
                continue
            staff_id = int(key[len(STATUS_FIELD_PREFIX):])
            overtime = _int_or(request.POST.get(f"overtime_{staff_id}"), 0)
            StaffAttendance.objects.update_or_create(
                staff_id=staff_id,
                date=date,
                defaults={
                    "status": value,
                    "check_in": _parse_time(request.POST.get(f"check_in_{staff_id}")),
                    "check_out": _parse_time(request.POST.get(f"check_out_{staff_id}")),
                    "overtime_minutes": max(overtime, 0),
                    "remark": request.POST.get(f"remark_{staff_id}", ""),
                    "marked_by": request.user,
                },
            )
            saved += 1
        audit(request, f"attendance.staff date={date} ({saved} staff)")
        messages.success(request, f"Staff attendance saved for {saved} staff on {date}.")
        return redirect(f"{request.path}?date={date}")

    date = _parse_date(request.GET.get("date"))
    members = Staff.objects.filter(status=Status.ACTIVE).order_by("first_name", "last_name")
    records = {
        rec.staff_id: rec
        for rec in StaffAttendance.objects.filter(date=date, staff__in=members)
    }
    rows = [{"staff": member, "record": records.get(member.pk)} for member in members]
    return render(
        request,
        "attendance/staff.html",
        {
            "date": date,
            "rows": rows,
            "statuses": StaffAttendanceStatus.choices,
            "page_title": "Staff Attendance",
            "page_subtitle": "Daily register with check-in/out and overtime",
            "active_page": "attendance",
        },
    )


@login_required
def attendance_reports(request):
    """Class/student/subject attendance analytics for a month."""

    today = datetime.date.today()
    klasses = Class.objects.order_by("name")
    klass_id = request.GET.get("klass") or ""
    year = _int_or(request.GET.get("year"), today.year)
    month = _int_or(request.GET.get("month"), today.month)
    month = month if 1 <= month <= 12 else today.month
    klass = klasses.filter(pk=klass_id).first() if klass_id.isdigit() else None

    context = {
        "klasses": klasses,
        "klass": klass,
        "selected_klass": klass_id,
        "year": year,
        "month": month,
        "month_choices": [(i, calendar.month_name[i]) for i in range(1, 13)],
        "year_choices": list(range(today.year - 2, today.year + 3)),
        "page_title": "Attendance Reports",
        "page_subtitle": "Class, student and subject attendance analytics",
        "active_page": "attendance",
    }
    if not klass:
        return render(request, "attendance/reports.html", context)

    students = list(_class_students(klass))
    start = datetime.date(year, month, 1)
    end = datetime.date(year, month, calendar.monthrange(year, month)[1])
    records = StudentAttendance.objects.filter(
        student__in=students, date__gte=start, date__lte=end, period__isnull=True
    )

    counts = {}
    for row in records.values("student_id", "status").annotate(count=Count("id")):
        counts.setdefault(row["student_id"], {})[row["status"]] = row["count"]

    student_rows = []
    present_total = 0
    marked_total = 0
    for student in students:
        data = counts.get(student.pk, {})
        present = data.get(AttendanceStatus.PRESENT, 0)
        total = sum(data.values())
        present_total += present
        marked_total += total
        student_rows.append(
            {
                "student": student,
                "present": present,
                "absent": data.get(AttendanceStatus.ABSENT, 0),
                "late": data.get(AttendanceStatus.LATE, 0),
                "leave": data.get(AttendanceStatus.LEAVE, 0),
                "excused": data.get(AttendanceStatus.EXCUSED, 0),
                "total": total,
                "percent": round(present / total * 100, 1) if total else 0,
            }
        )

    present_by_day = {
        row["date"]: row["count"]
        for row in records.filter(status=AttendanceStatus.PRESENT)
        .values("date")
        .annotate(count=Count("id"))
    }
    chart_labels = []
    chart_values = []
    denominator = len(students)
    for day in range(1, end.day + 1):
        present = present_by_day.get(datetime.date(year, month, day), 0)
        chart_labels.append(day)
        chart_values.append(round(present / denominator * 100, 1) if denominator else 0)

    subject_rows = []
    subject_qs = (
        PeriodAttendance.objects.filter(student__in=students, date__gte=start, date__lte=end)
        .values("subject__name")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=AttendanceStatus.PRESENT)),
        )
        .order_by("subject__name")
    )
    for row in subject_qs:
        total = row["total"] or 0
        subject_rows.append(
            {
                "subject": row["subject__name"] or "—",
                "total": total,
                "present": row["present"],
                "percent": round(row["present"] / total * 100, 1) if total else 0,
            }
        )

    context.update(
        {
            "students": students,
            "student_rows": student_rows,
            "subject_rows": subject_rows,
            "class_percent": round(present_total / marked_total * 100, 1) if marked_total else 0,
            "present_total": present_total,
            "marked_total": marked_total,
            "chart_labels": json.dumps(chart_labels),
            "chart_values": json.dumps(chart_values),
        }
    )
    return render(request, "attendance/reports.html", context)


@login_required
def attendance_total(request):
    """Cumulative yearly attendance for a single student."""

    year = _int_or(request.GET.get("year"), datetime.date.today().year)
    admission = (request.GET.get("admission") or "").strip()
    student = Student.objects.filter(admission_number=admission).first() if admission else None
    context = {
        "admission": admission,
        "year": year,
        "student": student,
        "page_title": "Student Attendance Total",
        "page_subtitle": "Cumulative annual attendance for one student",
        "active_page": "attendance",
    }
    if not student:
        return render(request, "attendance/total.html", context)

    records = StudentAttendance.objects.filter(
        student=student, date__year=year, period__isnull=True
    )
    counts = {}
    for row in records.values("status").annotate(count=Count("id")):
        counts[row["status"]] = row["count"]

    monthly = []
    chart_labels = []
    chart_values = []
    for month in range(1, 13):
        month_records = records.filter(date__month=month)
        present = month_records.filter(status=AttendanceStatus.PRESENT).count()
        total = month_records.count()
        pct = round(present / total * 100, 1) if total else 0
        monthly.append(
            {
                "month": calendar.month_name[month],
                "present": present,
                "total": total,
                "percent": pct,
            }
        )
        chart_labels.append(calendar.month_abbr[month])
        chart_values.append(pct)

    total_marked = sum(counts.values())
    context.update(
        {
            "counts": counts,
            "present": counts.get(AttendanceStatus.PRESENT, 0),
            "absent": counts.get(AttendanceStatus.ABSENT, 0),
            "late": counts.get(AttendanceStatus.LATE, 0),
            "leave": counts.get(AttendanceStatus.LEAVE, 0),
            "excused": counts.get(AttendanceStatus.EXCUSED, 0),
            "total_marked": total_marked,
            "percent": round(counts.get(AttendanceStatus.PRESENT, 0) / total_marked * 100, 1)
            if total_marked
            else 0,
            "monthly": monthly,
            "chart_labels": json.dumps(chart_labels),
            "chart_values": json.dumps(chart_values),
        }
    )
    return render(request, "attendance/total.html", context)


@login_required
def export_attendance(request):
    """CSV month summary for a class (same filters as reports)."""

    today = datetime.date.today()
    klass_id = request.GET.get("klass") or ""
    year = _int_or(request.GET.get("year"), today.year)
    month = _int_or(request.GET.get("month"), today.month)
    month = month if 1 <= month <= 12 else today.month
    klass = Class.objects.filter(pk=klass_id).first() if klass_id.isdigit() else None

    students = _class_students(klass) if klass else Student.objects.filter(status=Status.ACTIVE)
    students = students.order_by("admission_number")
    start = datetime.date(year, month, 1)
    end = datetime.date(year, month, calendar.monthrange(year, month)[1])
    records = StudentAttendance.objects.filter(
        student__in=students, date__gte=start, date__lte=end, period__isnull=True
    )
    counts = {}
    for row in records.values("student_id", "status").annotate(count=Count("id")):
        counts.setdefault(row["student_id"], {})[row["status"]] = row["count"]

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"attendance_{year}_{month:02d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        ["Admission No", "Student", "Class", "Present", "Absent", "Late", "Leave", "Excused", "Marked", "Percent"]
    )
    for student in students:
        data = counts.get(student.pk, {})
        present = data.get(AttendanceStatus.PRESENT, 0)
        total = sum(data.values())
        writer.writerow(
            [
                student.admission_number,
                student.full_name,
                student.klass.name if student.klass else "",
                present,
                data.get(AttendanceStatus.ABSENT, 0),
                data.get(AttendanceStatus.LATE, 0),
                data.get(AttendanceStatus.LEAVE, 0),
                data.get(AttendanceStatus.EXCUSED, 0),
                total,
                round(present / total * 100, 1) if total else 0,
            ]
        )
    audit(request, f"attendance.export class={klass} year={year} month={month}")
    return response
