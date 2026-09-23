import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q, Sum
from django.shortcuts import render

from apps.attendance.models import StudentAttendance


def _role_label(user):
    if user.is_superuser:
        return "admin"
    if user.role:
        return user.role.key
    # Fallback to linked records when no role is assigned yet.
    if getattr(user, "staff", None):
        return "staff"
    if getattr(user, "parent", None):
        return "parent"
    if getattr(user, "student", None):
        return "student"
    return "staff"


def _attendance_breakdown(qs, today):
    breakdown = list(qs.values("status").annotate(count=Count("id")))
    return {
        "breakdown": breakdown,
        "total": sum(item["count"] for item in breakdown),
    }


def _fee_balance(student):
    from apps.fees.models import FeePayment, FeeVoucherItem

    due = (
        FeeVoucherItem.objects.filter(voucher__student=student, voucher__status="issued")
        .annotate(net=F("amount") - F("discount"))
        .aggregate(total=Sum("net"))["total"]
        or 0
    )
    paid = (
        FeePayment.objects.filter(student=student).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    return due - paid


def _latest_result(student):
    return student.results.order_by("-exam__start_date", "-id").select_related("exam").first()


def _stats_for_role(user):
    stats = {}
    role_key = user.role.key if user.role else ""
    today = datetime.date.today()
    stats["role"] = _role_label(user)
    stats["weekday_today"] = today.strftime("%A")

    admin_roles = {
        "super_admin",
        "school_administrator",
        "principal",
        "vice_principal",
        "accountant",
    }
    if user.is_superuser or role_key in admin_roles:
        from apps.academics.models import Class as SchoolClass
        from apps.admissions.models import AdmissionInquiry
        from apps.exams.models import Exam
        from apps.fees.models import FeePayment
        from apps.notifications.models import Announcement
        from apps.parents.models import Parent
        from apps.staff.models import Staff
        from apps.students.models import Student

        stats.update(
            {
                "is_admin": True,
                "students_total": Student.objects.count(),
                "students_active": Student.objects.filter(status="active").count(),
                "admissions_pending": AdmissionInquiry.objects.filter(
                    status="pending"
                ).count(),
                "fees_collected_today": sum(
                    p.amount for p in FeePayment.objects.filter(paid_on=today)
                ),
                "parents_total": Parent.objects.count(),
                "teachers_total": Staff.objects.filter(is_teacher=True).count(),
                "staff_total": Staff.objects.count(),
                "classes_total": SchoolClass.objects.count(),
                "exams_total": Exam.objects.count(),
                "announcements_active": Announcement.objects.filter(
                    is_active=True
                ).count(),
                "routine_weekday": today.strftime("%A"),
            }
        )

    # Admin: today's attendance breakdown.
    stats.update(_attendance_breakdown(StudentAttendance.objects.filter(date=today), today))

    # Routine matrix (published timetable) for the selected weekday.
    from apps.academics.models import Class as SchoolClass
    from apps.timetable.models import Timetable, TimetableEntry

    published = Timetable.objects.filter(status="published").first()
    stats["routine_weekday"] = today.strftime("%A")
    stats["routine_periods"] = []
    stats["routine_grid"] = {}
    if published:
        periods = (
            TimetableEntry.objects.filter(timetable=published, weekday=str(today.weekday()))
            .values_list("period__id", "period__start_time", "period__order")
            .distinct()
            .order_by("period__order")
        )
        stats["routine_periods"] = [
            {
                "id": pid,
                "time": (st.strftime("%H:%M") if st else f"P{order}"),
                "order": order,
            }
            for pid, st, order in periods
        ]
        entries = TimetableEntry.objects.filter(
            timetable=published, weekday=str(today.weekday())
        )
        grid = {}
        for e in entries:
            grid.setdefault(e.klass_id, {})[e.period_id] = e
        stats["routine_grid"] = grid
        stats["routine_classes"] = list(
            SchoolClass.objects.filter(
                timetable_entries__timetable=published,
                timetable_entries__weekday=str(today.weekday()),
            ).distinct()
        )
    return stats


@login_required
def dashboard(request):
    """Role-aware landing page (spec §24)."""
    stats = _stats_for_role(request.user)
    ctx = {"stats": stats, "active_page": "dashboard"}
    _enrich_role_stats(request.user, stats)
    ctx["role_cards"] = _role_cards(request.user)
    return render(request, "core/dashboard.html", ctx)


def _linked_staff(user):
    return getattr(user, "staff", None)


def _linked_student(user):
    return getattr(user, "student", None)


def _linked_parent(user):
    return getattr(user, "parent", None)


def _enrich_role_stats(user, stats):
    """Fill role-specific blocks for teachers, parents and students (§24)."""
    staff = _linked_staff(user)
    parent = _linked_parent(user)
    student = _linked_student(user)
    today = datetime.date.today()

    if staff is not None or stats["role"] == "teacher":
        from apps.academics.models import Homework
        from apps.timetable.models import Timetable, TimetableEntry

        staff = staff or user.staff
        stats["my_staff"] = staff
        published = Timetable.objects.filter(status="published").first()
        stats["my_lessons_today"] = []
        if published and staff:
            stats["my_lessons_today"] = list(
                TimetableEntry.objects.filter(
                    timetable=published, teacher=staff, weekday=str(today.weekday())
                ).select_related("klass", "section", "subject", "period", "room")
                .order_by("period__order")
            )
        stats["my_homework"] = (
            Homework.objects.filter(teacher=staff)
            .select_related("klass", "section", "subject")
            .order_by("due_date")[:8]
            if staff
            else []
        )
        stats["homework_due_today"] = (
            Homework.objects.filter(teacher=staff, due_date=today).count() if staff else 0
        )
        from apps.discipline.models import Incident

        stats["my_incidents"] = (
            Incident.objects.filter(reported_by=user).order_by("-created_at")[:5]
            if hasattr(Incident, "reported_by")
            else []
        )

    if parent is not None or stats["role"] == "parent":
        from apps.attendance.models import StudentAttendance

        parent = parent or user.parent
        children = (parent.students.select_related("klass", "section") if parent else [])
        stats["my_parent"] = parent
        stats["my_children"] = list(children)
        stats["children_rows"] = []
        stats["children_present"] = 0
        stats["children_balance"] = 0
        stats["children_results"] = 0
        for child in stats["my_children"]:
            ab = _attendance_breakdown(
                StudentAttendance.objects.filter(student=child, date=today), today
            )
            row = {
                "student": child,
                "present": next(
                    (b["count"] for b in ab["breakdown"] if b["status"] == "present"), 0
                ),
                "marked": ab["total"],
                "balance": _fee_balance(child) if child.pk else 0,
                "latest": _latest_result(child),
            }
            stats["children_present"] += row["present"]
            stats["children_balance"] += row["balance"]
            if row["latest"]:
                stats["children_results"] += 1
            stats["children_rows"].append(row)

    if student is not None or stats["role"] == "student":
        from apps.attendance.models import AttendanceStatus, StudentAttendance

        student = student or user.student
        stats["my_student"] = student
        month_start = today.replace(day=1)
        my_att = StudentAttendance.objects.filter(
            student=student, date__gte=month_start
        )
        stats["monthly_marked"] = my_att.count()
        stats["monthly_present"] = my_att.filter(
            status=AttendanceStatus.PRESENT
        ).count()
        stats["monthly_rate"] = (
            round(
                stats["monthly_present"] / stats["monthly_marked"] * 100, 1
            )
            if stats["monthly_marked"]
            else 0
        )
        stats["fee_balance"] = _fee_balance(student) if student.pk else 0
        stats["latest_result"] = _latest_result(student)
        # Student's personal timetable today.
        from apps.timetable.models import Timetable, TimetableEntry

        published = Timetable.objects.filter(status="published").first()
        stats["my_timetable"] = []
        if published and student and student.klass_id:
            stats["my_timetable"] = list(
                TimetableEntry.objects.filter(
                    timetable=published,
                    klass_id=student.klass_id,
                    weekday=str(today.weekday()),
                )
                .select_related("subject", "teacher", "period", "room")
                .order_by("period__order")
            )


def _role_cards(user):
    """Quick links relevant to the current role (§24)."""
    cards = []
    role = _role_label(user)
    if role == "admin":
        cards = [
            {"label": "Students", "icon": "people", "url": "students:list"},
            {"label": "Timetable", "icon": "calendar-week", "url": "timetable:index"},
            {"label": "Fees", "icon": "cash-coin", "url": "fees:heads"},
            {"label": "Attendance", "icon": "calendar-check", "url": "attendance:list"},
            {"label": "Exams & Results", "icon": "clipboard-data", "url": "results:list"},
            {"label": "Reports", "icon": "graph-up", "url": "reports:list"},
            {"label": "Staff & HR", "icon": "person-badge", "url": "hr:employees"},
            {"label": "Library", "icon": "journal-bookmark", "url": "library:list"},
        ]
    elif role == "teacher":
        cards = [
            {"label": "Attendance", "icon": "calendar-check", "url": "attendance:mark"},
            {"label": "Homework", "icon": "journal-text", "url": "academics:homework"},
            {"label": "Timetable", "icon": "calendar-week", "url": "timetable:index"},
            {"label": "Classes", "icon": "chalkboard", "url": "academics:classes"},
            {"label": "Marks", "icon": "clipboard-data", "url": "exams:marks_entry"},
            {"label": "Discipline", "icon": "shield-exclamation", "url": "discipline:student"},
        ]
    elif role == "parent":
        cards = [
            {"label": "My Children", "icon": "people", "url": "parents:list"},
            {"label": "Fees", "icon": "cash-coin", "url": "fees:heads"},
            {"label": "Progress", "icon": "graph-up", "url": "progress:list"},
            {"label": "Notices", "icon": "bell", "url": "notifications:inbox"},
        ]
    elif role == "student":
        cards = [
            {"label": "My Timetable", "icon": "calendar-week", "url": "timetable:index"},
            {"label": "Homework", "icon": "journal-text", "url": "academics:homework"},
            {"label": "Results", "icon": "clipboard-data", "url": "results:list"},
            {"label": "Notifications", "icon": "bell", "url": "notifications:inbox"},
        ]
    return cards


@login_required
def module_placeholder(request, module):
    """Generic page for modules whose views are not implemented yet."""
    labels = {
        "students": "Students",
        "parents": "Parents",
        "admissions": "Admissions",
        "timetable": "Automatic Timetable",
        "attendance": "Attendance",
        "exams": "Exams & Results",
        "fees": "Fees & Finance",
        "staff": "Staff & HR",
        "houses": "Houses",
        "library": "Library",
        "transport": "Transport",
        "inventory": "Inventory",
        "reports": "Reports",
        "communication": "Communication",
    }
    return render(
        request,
        "core/module_placeholder.html",
        {
            "module": module,
            "module_label": labels.get(module, module.replace("_", " ").title()),
            "active_page": "module",
        },
    )


PER_PAGE = 20


@login_required
def global_search(request):
    """Global search across students, staff and classes (topbar 'Search..')."""
    q = request.GET.get("q", "").strip()
    students, staff, classes = [], [], []
    if q:
        from apps.academics.models import Class as SchoolClass
        from apps.staff.models import Staff
        from apps.students.models import Student

        students = (
            Student.objects.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(middle_name__icontains=q)
                | Q(admission_number__icontains=q)
                | Q(roll_number__icontains=q)
            )
            .select_related("klass", "section")[:PER_PAGE]
        )
        staff = (
            Staff.objects.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(middle_name__icontains=q)
                | Q(employee_code__icontains=q)
                | Q(designation__icontains=q)
            )[:PER_PAGE]
        )
        classes = SchoolClass.objects.filter(name__icontains=q)[:10]
    return render(
        request,
        "core/search.html",
        {
            "q": q,
            "students": students,
            "staff": staff,
            "classes": classes,
            "active_page": "search",
        },
    )