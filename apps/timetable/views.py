import datetime
import time

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, FormView, ListView, TemplateView

from apps.academics.models import Class, Period, Room, Subject, SubjectAllocation
from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.school.models import AcademicYear, Holiday, Weekday, WorkingDay
from apps.staff.models import Staff

from .forms import CellEditForm, GenerateTimetableForm, RegenerateTimetableForm
from .models import (
    TeacherAvailability,
    TeacherPreference,
    Timetable,
    TimetableEntry,
    TimetableStatus,
)
from .services import conflicts_report, generate_timetable, regenerate_timetable

FALLBACK_DAYS = ["1", "2", "3", "4", "5"]


def _resolve_url(name, *args):
    try:
        return reverse(name, args=args)
    except Exception:
        return "#"


def _detail_url(pk, tab=None, oid=None):
    path = reverse("timetable:detail", args=[pk])
    if tab:
        path += f"?tab={tab}"
        if oid:
            path += f"&oid={oid}"
    return path


def _day_defs(entries):
    codes = sorted({e.weekday for e in entries}, key=int)
    if not codes:
        codes = FALLBACK_DAYS
    labels = dict(Weekday.choices)
    return [{"code": c, "label": labels[c]} for c in codes]


def _periods_for_grid():
    return list(Period.objects.filter(is_break=False).order_by("order"))


def _grid_rows(entries, periods, day_defs, matches):
    rows = []
    for period in periods:
        cells = []
        for day_def in day_defs:
            entry = None
            for e in entries:
                if e.weekday == day_def["code"] and e.period_id == period.pk and matches(e):
                    entry = e
                    break
            cells.append({"day": day_def["code"], "entry": entry})
        rows.append({"period": period, "cells": cells})
    return rows


def _master_rows(entries, periods, day_defs):
    by_class = {}
    for e in entries:
        by_class.setdefault(e.klass, []).append(e)
    rows = []
    for klass in sorted(by_class, key=lambda c: c.name):
        cells = []
        for day_def in day_defs:
            items = sorted(
                [e for e in by_class[klass] if e.weekday == day_def["code"]],
                key=lambda e: (e.period.order, e.period.start_time),
            )
            cells.append({"day": day_def["code"], "items": items})
        rows.append({"klass": klass, "cells": cells})
    return rows


def _pick(items, oid, key):
    if not items:
        return None
    if oid is not None:
        for item in items:
            if key(item) == oid:
                return item
    return items[0]


class IndexView(EdFlowMixin, TemplateView):
    template_name = "timetable/index.html"
    page_title = "Automatic Timetable"
    page_subtitle = "Deterministic offline generation via OR-Tools CP-SAT"
    active_page = "timetable"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = AcademicYear.objects.filter(is_active=True).first()
        today = datetime.date.today()

        readiness = [
            (
                "Academic year configured",
                bool(year),
                _resolve_url("school:academic_year_add"),
            ),
            (
                "Working days set",
                bool(year and year.working_days.exists()),
                _resolve_url("school:working_day_add"),
            ),
            (
                "Periods defined",
                Period.objects.exists(),
                _resolve_url("admin:academics_period_changelist"),
            ),
            (
                "Teachers registered",
                Staff.objects.filter(is_teacher=True).exists(),
                _resolve_url("staff:list"),
            ),
            (
                "Classes with subject allocations",
                bool(
                    SubjectAllocation.objects.filter(periods_per_week__gt=0)
                    .values("klass")
                    .distinct()
                    .exists()
                ),
                _resolve_url("academics:classes"),
            ),
            (
                "Rooms available",
                Room.objects.exists(),
                _resolve_url("academics:rooms"),
            ),
        ]
        ctx.update(
            {
                "year": year,
                "today": today,
                "readiness": [
                    {"label": label, "ok": ok, "url": url}
                    for label, ok, url in readiness
                ],
                "timetables": (
                    Timetable.objects.select_related("academic_year", "term")
                    .annotate(
                        entry_count=Count("entries", distinct=True),
                        locked_count=Count("entries", filter=Q(entries__is_locked=True)),
                    )
                    .all()
                ),
                "status_choices": TimetableStatus.choices,
                "classes_total": Class.objects.count(),
                "subjects_total": Subject.objects.count(),
                "teachers_total": Staff.objects.filter(is_teacher=True).count(),
                "holidays_total": Holiday.objects.filter(academic_year=year).count() if year else 0,
            }
        )
        return ctx


class TimetableListView(EdFlowMixin, SearchMixin, ListView):
    model = Timetable
    template_name = "timetable/list.html"
    context_object_name = "timetables"
    paginate_by = 25
    page_title = "Timetables"
    page_subtitle = "Generated versions with status workflow"
    active_page = "timetable"
    search_fields = ["name"]
    search_placeholder = "Search timetables…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("academic_year", "term")
        status = self.request.GET.get("status", "")
        if status in dict(TimetableStatus.choices):
            qs = qs.filter(status=status)
        return qs.annotate(
            entry_count=Count("entries", distinct=True),
            locked_count=Count("entries", filter=Q(entries__is_locked=True)),
        ).order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = TimetableStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        return ctx


class TimetableGenerateView(EdFlowMixin, FormView):
    template_name = "timetable/generate.html"
    form_class = GenerateTimetableForm
    page_title = "Generate Timetable"
    page_subtitle = "One-click automatic scheduling powered by OR-Tools CP-SAT"
    active_page = "timetable"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = AcademicYear.objects.filter(is_active=True).first()
        steps = [
            {
                "num": 1,
                "label": "Configure academic structure",
                "url": _resolve_url("school:academic_year_add"),
                "ok": bool(year),
            },
            {
                "num": 2,
                "label": "Configure teachers",
                "url": _resolve_url("staff:list"),
                "ok": Staff.objects.filter(is_teacher=True).exists(),
            },
            {
                "num": 3,
                "label": "Configure subjects",
                "url": _resolve_url("academics:subjects"),
                "ok": Subject.objects.exists(),
            },
            {
                "num": 4,
                "label": "Configure rooms",
                "url": _resolve_url("academics:rooms"),
                "ok": Room.objects.exists(),
            },
            {
                "num": 5,
                "label": "Configure periods",
                "url": _resolve_url("admin:academics_period_changelist"),
                "ok": Period.objects.exists(),
            },
            {
                "num": 6,
                "label": "Configure teacher availability",
                "url": _resolve_url("admin:timetable_teacheravailability_changelist"),
                "ok": TeacherAvailability.objects.exists()
                or Staff.objects.filter(is_teacher=True).exists(),
            },
            {
                "num": 7,
                "label": "Configure subject requirements",
                "url": _resolve_url("admin:academics_subjectallocation_changelist"),
                "ok": SubjectAllocation.objects.filter(periods_per_week__gt=0).exists(),
            },
            {
                "num": 8,
                "label": "Configure school preferences",
                "url": _resolve_url("admin:timetable_teacherpreference_changelist"),
                "ok": True,
            },
        ]
        ctx["steps"] = steps
        ctx["working_days"] = list(
            WorkingDay.objects.filter(academic_year=year).values_list("weekday", flat=True)
            if year
            else []
        )
        ctx["all_ready"] = all(step["ok"] for step in steps)
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        started = time.perf_counter()
        try:
            status = generate_timetable(
                timetable_name=data["name"],
                academic_year=data["academic_year"],
                term=data.get("term"),
                classes=list(data["classes"]),
                max_seconds=data["max_seconds"],
                note=data.get("note", ""),
                created_by=self.request.user,
            )
        except Exception as exc:
            audit(self.request, f"timetable.generate_error name={data['name']} error={exc}")
            messages.error(self.request, f"Generation failed: {exc}")
            return redirect("timetable:index")

        duration = time.perf_counter() - started
        audit(
            self.request,
            f"timetable.generate id={status['timetable'].pk} "
            f"ok={status['ok']} status={status['status']} duration={duration:.1f}s",
        )
        if status["ok"]:
            messages.success(
                self.request,
                f"Timetable generated with {status['entries']} entries in {duration:.1f}s.",
            )
        else:
            messages.error(
                self.request,
                "Generation did not fully succeed — review the infeasibility report.",
            )
        return redirect("timetable:result", pk=status["timetable"].pk)


class TimetableResultView(EdFlowMixin, DetailView):
    model = Timetable
    template_name = "timetable/result.html"
    context_object_name = "timetable"
    active_page = "timetable"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        summary = self.object.constraints_summary or {}
        ctx["page_title"] = f"Result — {self.object.name}"
        ctx["page_subtitle"] = self.object.get_status_display()
        ctx["summary"] = summary
        return ctx


class TimetableDetailView(EdFlowMixin, DetailView):
    model = Timetable
    template_name = "timetable/detail.html"
    context_object_name = "timetable"
    active_page = "timetable"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tt = self.object
        entries = list(
            tt.entries.select_related("klass", "section", "subject", "teacher", "room", "period")
        )
        day_defs = _day_defs(entries)
        periods = _periods_for_grid()

        classes = sorted({e.klass for e in entries}, key=lambda c: c.name)
        teachers = sorted({e.teacher for e in entries}, key=lambda t: t.full_name)
        rooms = sorted({e.room for e in entries}, key=lambda r: r.name)

        tab = self.request.GET.get("tab", "class")
        if tab not in ("class", "teacher", "room", "master"):
            tab = "class"
        oid_raw = self.request.GET.get("oid")
        oid = int(oid_raw) if oid_raw and oid_raw.isdigit() else None

        grid_rows = []
        master_rows = []
        selected = None

        if tab == "teacher":
            selected = _pick(teachers, oid, lambda t: t.pk)
            if selected:
                grid_rows = _grid_rows(
                    entries, periods, day_defs, lambda e: e.teacher_id == selected.pk
                )
        elif tab == "room":
            selected = _pick(rooms, oid, lambda r: r.pk)
            if selected:
                grid_rows = _grid_rows(
                    entries, periods, day_defs, lambda e: e.room_id == selected.pk
                )
        elif tab == "master":
            master_rows = _master_rows(entries, periods, day_defs)
        else:
            selected = _pick(classes, oid, lambda c: c.pk)
            if selected:
                grid_rows = _grid_rows(
                    entries, periods, day_defs, lambda e: e.klass_id == selected.pk
                )

        ctx.update(
            {
                "page_title": tt.name,
                "page_subtitle": f"{tt.academic_year.name} · {tt.get_status_display()}",
                "tab": tab,
                "selected": selected,
                "day_defs": day_defs,
                "periods_grid": periods,
                "grid_rows": grid_rows,
                "master_rows": master_rows,
                "classes_opts": classes,
                "teachers_opts": teachers,
                "rooms_opts": rooms,
                "all_classes": Class.objects.all(),
                "all_periods": periods,
                "all_subjects": Subject.objects.all(),
                "all_teachers": Staff.objects.filter(is_teacher=True),
                "all_rooms": Room.objects.all(),
                "weekday_choices": Weekday.choices,
                "tab_choices": (
                    ("class", "Class grid"),
                    ("teacher", "Teacher grid"),
                    ("room", "Room grid"),
                    ("master", "Master timetable"),
                ),
                "entries_total": len(entries),
                "conflicts": conflicts_report(tt),
                "has_entries": bool(entries),
                "regenerate_form": RegenerateTimetableForm(
                    default_seconds=30,
                    klass_id=selected.pk if tab == "class" and selected else None,
                    teacher_id=selected.pk if tab == "teacher" and selected else None,
                    weekday=self.request.GET.get("day") or None,
                ),
            }
        )
        return ctx


class TimetablePrintView(EdFlowMixin, DetailView):
    model = Timetable
    template_name = "timetable/print.html"
    context_object_name = "timetable"
    active_page = "timetable"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tt = self.object
        entries = list(
            tt.entries.select_related("klass", "section", "subject", "teacher", "room", "period")
        )
        day_defs = _day_defs(entries)
        periods = _periods_for_grid()

        class_grids = []
        for klass in sorted({e.klass for e in entries}, key=lambda c: c.name):
            class_grids.append(
                {
                    "klass": klass,
                    "rows": _grid_rows(
                        entries, periods, day_defs, lambda e, k=klass: e.klass_id == k.pk
                    ),
                }
            )
        ctx.update(
            {
                "page_title": tt.name,
                "page_subtitle": f"{tt.academic_year.name} · {tt.get_status_display()}",
                "day_defs": day_defs,
                "periods_grid": periods,
                "class_grids": class_grids,
                "academic_year": tt.academic_year,
            }
        )
        return ctx


class CellEditView(EdFlowMixin, View):
    def post(self, request, pk):
        tt = get_object_or_404(Timetable, pk=pk)
        form = CellEditForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid cell data submitted.")
            return redirect("timetable:detail", pk=tt.pk)

        data = form.cleaned_data
        klass = data["klass"]
        existing = (
            tt.entries.filter(klass=klass, weekday=data["weekday"], period=data["period"]).first()
        )
        if existing and existing.is_locked:
            messages.error(request, "That cell is locked — unlock it before editing.")
            return redirect(_detail_url(tt.pk, "class", klass.pk))

        if not SubjectAllocation.objects.filter(
            klass=klass,
            subject=data["subject"],
            teacher=data["teacher"],
            periods_per_week__gt=0,
        ).exists():
            messages.error(
                request,
                f"{data['teacher']} teaches {data['subject']} in {klass} but no allocation exists.",
            )
            return redirect(_detail_url(tt.pk, "class", klass.pk))

        clashes = tt.entries.filter(weekday=data["weekday"], period=data["period"]).exclude(
            klass=klass
        )
        problems = []
        if clashes.filter(teacher=data["teacher"]).exists():
            problems.append("teacher already booked in that slot")
        if clashes.filter(room=data["room"]).exists():
            problems.append("room already booked in that slot")
        if TeacherAvailability.objects.filter(
            teacher=data["teacher"], weekday=data["weekday"], available=False
        ).exists():
            problems.append("teacher unavailable on that weekday")
        if problems:
            audit(
                request,
                f"timetable.cell_rejected id={tt.pk} klass={klass} problems={'; '.join(problems)}",
            )
            messages.error(request, "Conflict: " + "; ".join(problems))
            return redirect(_detail_url(tt.pk, "class", klass.pk))

        if existing:
            existing.subject = data["subject"]
            existing.teacher = data["teacher"]
            existing.room = data["room"]
            existing.is_locked = False
            existing.save(update_fields=["subject", "teacher", "room", "is_locked"])
        else:
            TimetableEntry.objects.create(
                timetable=tt,
                weekday=data["weekday"],
                period=data["period"],
                klass=klass,
                section=None,
                subject=data["subject"],
                teacher=data["teacher"],
                room=data["room"],
            )
        audit(
            request,
            f"timetable.cell_edit id={tt.pk} klass={klass} {data['weekday']} P{data['period'].order} "
            f"{data['subject']} {data['teacher']}",
        )
        messages.success(request, f"Cell updated — {data['subject']} with {data['teacher']}.")
        return redirect(_detail_url(tt.pk, "class", klass.pk))


class LockCellView(EdFlowMixin, View):
    def post(self, request, pk):
        entry = get_object_or_404(TimetableEntry, pk=pk)
        entry.is_locked = True
        entry.save(update_fields=["is_locked"])
        audit(request, f"timetable.cell_lock id={entry.pk}")
        messages.success(request, "Cell locked — it will be preserved on regeneration.")
        return redirect("timetable:detail", pk=entry.timetable_id)


class UnlockCellView(EdFlowMixin, View):
    def post(self, request, pk):
        entry = get_object_or_404(TimetableEntry, pk=pk)
        entry.is_locked = False
        entry.save(update_fields=["is_locked"])
        audit(request, f"timetable.cell_unlock id={entry.pk}")
        messages.success(request, "Cell unlocked.")
        return redirect("timetable:detail", pk=entry.timetable_id)


class TimetableRegenerateView(EdFlowMixin, View):
    """Selectively re-run the solver for chosen classes/teachers/days (§9)."""

    def post(self, request, pk):
        tt = get_object_or_404(Timetable, pk=pk)
        if tt.status == TimetableStatus.ARCHIVED:
            messages.error(request, "Archived timetables cannot be regenerated.")
            return redirect("timetable:detail", pk=tt.pk)

        form = RegenerateTimetableForm(request.POST, default_seconds=30)
        if not form.is_valid():
            messages.error(request, "Invalid regeneration scope.")
            return redirect("timetable:detail", pk=tt.pk)

        data = form.cleaned_data
        scope_classes = list(data["classes"].values_list("pk", flat=True))
        scope_teachers = list(data["teachers"].values_list("pk", flat=True))
        scope_days = data["days"]

        try:
            result = regenerate_timetable(
                timetable=tt,
                classes=scope_classes or None,
                teachers=scope_teachers or None,
                days=scope_days or None,
                max_seconds=data["max_seconds"],
                note=data.get("note", ""),
                created_by=request.user,
            )
        except Exception as exc:
            audit(request, f"timetable.regenerate_error id={tt.pk} error={exc}")
            messages.error(request, f"Regeneration failed: {exc}")
            return redirect("timetable:result", pk=tt.pk)

        audit(
            request,
            f"timetable.regenerate id={tt.pk} ok={result['ok']} status={result['status']} "
            f"rebuilt={result['rebuilt']} scope=classes{scope_classes}/teachers{scope_teachers}/days{scope_days}",
        )
        if result["status"] == "noop":
            messages.info(request, "Nothing matched that scope — no cells were regenerated.")
        elif result["ok"]:
            messages.success(
                request,
                f"Regenerated {result['rebuilt']} cell(s) in {result['duration']:.1f}s "
                "using CP-SAT; locked and out-of-scope cells were preserved.",
            )
        else:
            messages.error(
                request,
                "Regeneration did not fully succeed — review the infeasibility report.",
            )
        return redirect("timetable:result", pk=tt.pk)


class MoveCellView(EdFlowMixin, View):
    """Drag-and-drop cell move/swap with immediate conflict detection (§9)."""

    def post(self, request, pk):
        tt = get_object_or_404(Timetable, pk=pk)
        entry = get_object_or_404(TimetableEntry, pk=request.POST.get("entry"))
        if entry.timetable_id != tt.pk:
            messages.error(request, "That cell does not belong to this timetable.")
            return redirect("timetable:detail", pk=tt.pk)
        if entry.is_locked:
            messages.error(request, "That cell is locked — unlock it before moving it.")
            return redirect(_detail_url(tt.pk, "class", entry.klass_id))

        move_to = {"day": request.POST.get("move_to_day"), "period": request.POST.get("move_to_period")}
        if not move_to["day"] or not move_to["period"] or not move_to["day"].isdigit():
            messages.error(request, "Drop target missing.")
            return redirect(_detail_url(tt.pk, "class", entry.klass_id))

        existing = tt.entries.filter(
            klass=entry.klass,
            weekday=move_to["day"],
            period=move_to["period"],
        ).first()

        if existing:
            return self._swap(request, tt, entry, existing)

        target_period = get_object_or_404(Period, pk=move_to["period"])
        problems = self._conflicts(tt, entry.klass, move_to["day"], target_period, entry, entry.teacher, entry.room)
        if problems:
            messages.error(request, "Conflict: " + "; ".join(problems))
            return redirect(_detail_url(tt.pk, "class", entry.klass_id))

        old_day, old_period = entry.weekday, entry.period
        entry.weekday = move_to["day"]
        entry.period = target_period
        entry.save(update_fields=["weekday", "period"])
        audit(
            request,
            f"timetable.cell_move id={entry.pk} {entry.get_weekday_display()} P{old_period.order}"
            f" -> {entry.get_weekday_display()} P{target_period.order}",
        )
        messages.success(request, f"Cell moved to {entry.get_weekday_display()} P{target_period.order}.")
        return redirect(_detail_url(tt.pk, "class", entry.klass_id))

    def _swap(self, request, tt, a, b):
        if b.is_locked:
            messages.error(request, "The drop target is locked — unlock it first.")
            return redirect(_detail_url(tt.pk, "class", a.klass_id))
        if a.klass_id != b.klass_id:
            messages.error(request, "You can only move cells within the same class grid.")
            return redirect(_detail_url(tt.pk, "class", a.klass_id))

        problems = []
        problems += self._conflicts(tt, a.klass, a.weekday, a.period, b, b.teacher, b.room)
        problems += self._conflicts(tt, a.klass, b.weekday, b.period, a, a.teacher, a.room)
        if problems:
            messages.error(request, "Conflict: " + "; ".join(set(problems)))
            return redirect(_detail_url(tt.pk, "class", a.klass_id))

        a.swap_with(b)
        audit(request, f"timetable.cell_swap id={a.pk} <-> id={b.pk}")
        messages.success(
            request,
            f"Swapped {a.subject} and {b.subject} (P{a.period.order}/P{b.period.order}).",
        )
        return redirect(_detail_url(tt.pk, "class", a.klass_id))

    def _conflicts(self, tt, klass, day, period, ignore_entry, teacher, room):
        problems = []
        same_slot = tt.entries.filter(weekday=day, period=period).exclude(
            klass=klass
        )
        if same_slot.filter(teacher=teacher).exclude(pk=ignore_entry.pk).exists():
            problems.append(f"{teacher} is already booked in that slot")
        if same_slot.filter(room=room).exclude(pk=ignore_entry.pk).exists():
            problems.append(f"{room} is already booked in that slot")
        if TeacherAvailability.objects.filter(
            teacher=teacher, weekday=day, available=False
        ).exists():
            problems.append(f"{teacher} is unavailable on that weekday")
        return problems


class TimetableApproveView(EdFlowMixin, View):
    def post(self, request, pk):
        tt = get_object_or_404(Timetable, pk=pk)
        if tt.status == TimetableStatus.ARCHIVED:
            messages.error(request, "Archived timetables cannot be approved.")
            return redirect("timetable:detail", pk=tt.pk)
        tt.status = TimetableStatus.APPROVED
        tt.save(update_fields=["status", "updated_at"])
        audit(request, f"timetable.approve id={tt.pk} name={tt.name}")
        messages.success(request, f"{tt.name} approved.")
        return redirect("timetable:detail", pk=tt.pk)


class TimetablePublishView(EdFlowMixin, View):
    def post(self, request, pk):
        tt = get_object_or_404(Timetable, pk=pk)
        if tt.status == TimetableStatus.ARCHIVED:
            messages.error(request, "Archived timetables cannot be published.")
            return redirect("timetable:detail", pk=tt.pk)
        with transaction.atomic():
            Timetable.objects.filter(status=TimetableStatus.PUBLISHED).exclude(
                pk=tt.pk
            ).update(status=TimetableStatus.ARCHIVED)
            tt.status = TimetableStatus.PUBLISHED
            tt.save(update_fields=["status", "updated_at"])
        audit(request, f"timetable.publish id={tt.pk} name={tt.name}")
        messages.success(request, f"{tt.name} published; other published timetables archived.")
        return redirect("timetable:detail", pk=tt.pk)


class TimetableArchiveView(EdFlowMixin, View):
    def post(self, request, pk):
        tt = get_object_or_404(Timetable, pk=pk)
        if tt.status != TimetableStatus.ARCHIVED:
            tt.status = TimetableStatus.ARCHIVED
            tt.save(update_fields=["status", "updated_at"])
            audit(request, f"timetable.archive id={tt.pk} name={tt.name}")
            messages.success(request, f"{tt.name} archived.")
        return redirect("timetable:detail", pk=tt.pk)


class TimetableDeleteView(EdFlowMixin, DeleteView):
    model = Timetable
    template_name = "timetable/confirm_delete.html"
    context_object_name = "timetable"
    success_url = reverse_lazy("timetable:list")
    active_page = "timetable"

    def form_valid(self, form):
        audit(self.request, f"timetable.delete id={self.object.pk} name={self.object.name}")
        messages.success(self.request, f"Timetable {self.object.name} deleted.")
        return super().form_valid(form)