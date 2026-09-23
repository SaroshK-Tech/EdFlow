"""Timetable generation orchestration and post-generation sanity checks."""

import time
from collections import Counter, defaultdict

from django.db import transaction
from django.utils import timezone

from apps.academics.models import Class, Period, Room, Subject, SubjectAllocation
from apps.school.models import Weekday, WorkingDay

from .generator import Requirement, Solver
from .models import TeacherAvailability, TeacherPreference, Timetable, TimetableEntry, TimetableStatus

FALLBACK_DAYS = ["1", "2", "3", "4", "5"]


def _working_weekdays(academic_year):
    if academic_year:
        codes = list(
            WorkingDay.objects.filter(academic_year=academic_year).values_list("weekday", flat=True)
        )
        valid = [c for c in codes if c in dict(Weekday.choices)]
        if valid:
            return sorted(valid, key=int)
    return list(FALLBACK_DAYS)


def regenerate_timetable(
    timetable,
    classes=None,
    teachers=None,
    days=None,
    max_seconds=30,
    note="",
    created_by=None,
):
    """Re-run the CP-SAT solver for selected classes/teachers/days only.

    Locked cells are always preserved. Cells *outside* the requested scope are
    also kept and are passed to the solver as blocked teacher/room slots so the
    re-created cells cannot double-book anything that stays in place.

    ``classes``, ``teachers`` and ``days`` are optional iterables; when None
    they mean "all". Passing at least one narrows the regeneration to that
    subset (spec §9: regenerate only selected classes / teachers / days).
    """
    started = time.perf_counter()
    tt = timetable

    entries = list(
        tt.entries.select_related("klass", "section", "subject", "teacher", "room", "period")
    )

    def _in_scope(e):
        if classes is not None and e.klass_id in classes:
            return True
        if teachers is not None and e.teacher_id in teachers:
            return True
        if days is not None and e.weekday in days:
            return True
        return False

    affected = [e for e in entries if _in_scope(e) and not e.is_locked]
    preserved = [e for e in entries if not _in_scope(e) or e.is_locked]

    scope_classes = sorted({e.klass_id for e in affected})
    if not scope_classes:
        summary = dict(tt.constraints_summary or {})
        summary.update(
            {
                "status": "noop",
                "satisfied": True,
                "solver_seconds": 0.0,
                "objective": 0.0,
                "regenerated_scope": {
                    "classes": sorted(classes) if classes is not None else None,
                    "teachers": sorted(teachers) if teachers is not None else None,
                    "days": sorted(days) if days is not None else None,
                },
                "rebuilt_cells": 0,
                "preserved_cells": len(preserved),
                "free_slots": tt.entries.count(),
                "soft_conflicts": [],
                "infeasibility_reasons": [],
                "note": note,
                "generated_at": timezone.now().isoformat(),
            }
        )
        tt.constraints_summary = summary
        tt.save(update_fields=["constraints_summary", "updated_at"])
        return {
            "timetable": tt,
            "ok": True,
            "status": "noop",
            "duration": time.perf_counter() - started,
            "solver_seconds": 0.0,
            "conflicts": [],
            "infeasible": [],
            "entries": tt.entries.count(),
            "rebuilt": 0,
        }

    periods = list(Period.objects.filter(is_break=False).order_by("order"))
    days_used = _working_weekdays(tt.academic_year)

    classes_objs = list(Class.objects.filter(pk__in=scope_classes))
    rooms = list(Room.objects.all())
    fallback_room = None
    fallback_created = False
    if not rooms:
        fallback_room, fallback_created = Room.objects.get_or_create(
            name="Room A", defaults={"room_type": "classroom"}
        )
        rooms = [fallback_room]

    requirements = []
    allocations = list(
        SubjectAllocation.objects.filter(
            klass__in=classes_objs, periods_per_week__gt=0
        ).select_related("klass", "subject", "teacher")
    )
    for a in allocations:
        requirements.append(
            Requirement(
                klass=a.klass,
                subject=a.subject,
                teacher=a.teacher,
                periods_per_week=a.periods_per_week,
                requires_lab=a.requires_lab,
            )
        )

    availability = {}
    for row in TeacherAvailability.objects.filter(available=False).values("teacher_id", "weekday"):
        availability[(row["teacher_id"], str(row["weekday"]))] = False

    prefs = []
    for row in TeacherPreference.objects.select_related("teacher", "subject"):
        prefs.append(
            {
                "teacher_id": row.teacher_id,
                "subject_id": row.subject_id,
                "after_lunch": row.after_lunch,
            }
        )

    locked = [
        {
            "klass": e.klass,
            "weekday": e.weekday,
            "period": e.period,
            "subject": e.subject,
            "teacher": e.teacher,
            "room": e.room,
        }
        for e in preserved
        if e.klass_id in scope_classes
    ]

    blocked = [
        {
            "weekday": e.weekday,
            "period": e.period,
            "teacher_id": e.teacher_id,
            "room_id": e.room_id,
        }
        for e in preserved
        if e.klass_id not in scope_classes
    ]

    solver = Solver(
        classes=classes_objs,
        days=days_used,
        periods=periods,
        requirements=requirements,
        rooms=rooms,
        locked=locked,
        availability=availability,
        preferences=prefs,
        blocked=blocked,
        max_time_seconds=max_seconds,
    )
    result = solver.solve()

    if result.satisfied:
        with transaction.atomic():
            tt.entries.filter(pk__in=[e.pk for e in affected]).delete()
            kept_keys = {
                (e.weekday, e.period_id, e.klass_id, e.section_id) for e in preserved
            }
            rows = []
            for a in result.assignments:
                key = (a["weekday"], a["period"].pk, a["klass"].pk, None)
                if key in kept_keys:
                    continue
                rows.append(
                    TimetableEntry(
                        timetable=tt,
                        weekday=a["weekday"],
                        period=a["period"],
                        klass=a["klass"],
                        section=None,
                        subject=a["subject"],
                        teacher=a["teacher"],
                        room=a["room"],
                    )
                )
            TimetableEntry.objects.bulk_create(rows)

    total_slots = len(scope_classes) * len(days_used) * len(periods)
    summary = dict(tt.constraints_summary or {})
    summary.update(
        {
            "status": result.status,
            "satisfied": result.satisfied,
            "solver_seconds": round(result.duration, 3),
            "objective": result.objective,
            "regenerated_scope": {
                "classes": sorted(classes) if classes is not None else None,
                "teachers": sorted(teachers) if teachers is not None else None,
                "days": sorted(days) if days is not None else None,
            },
            "rebuilt_cells": len(affected),
            "preserved_cells": len(preserved),
            "free_slots": max(0, total_slots - len(affected)),
            "soft_conflicts": result.soft_conflicts,
            "infeasibility_reasons": result.infeasible_reasons,
            "params": {
                "random_seed": 42,
                "max_time_seconds": max_seconds,
                "num_search_workers": 4,
                "consecutive_limit": 3,
            },
            "note": note,
            "generated_at": timezone.now().isoformat(),
        }
    )
    tt.constraints_summary = summary
    tt.save(update_fields=["constraints_summary", "updated_at"])

    return {
        "timetable": tt,
        "ok": result.satisfied,
        "status": result.status,
        "duration": time.perf_counter() - started,
        "solver_seconds": result.duration,
        "conflicts": result.soft_conflicts,
        "infeasible": result.infeasible_reasons,
        "entries": tt.entries.count(),
        "rebuilt": len(affected),
    }


def generate_timetable(
    timetable_name,
    academic_year,
    term=None,
    classes=None,
    max_seconds=30,
    note="",
    created_by=None,
):
    """Run the CP-SAT solver and persist the resulting entries to the timetable.

    Locked cells of an existing timetable with the same name/year are preserved
    and passed to the solver as fixed assignments.
    """
    started = time.perf_counter()

    days = _working_weekdays(academic_year)
    periods = list(Period.objects.filter(is_break=False).order_by("order"))

    if classes is None:
        classes = list(
            Class.objects.filter(subject_allocations__periods_per_week__gt=0).distinct()
        )
    classes = list(dict((c.pk, c) for c in classes).values())

    if not classes:
        classes = list(Class.objects.all())

    rooms = list(Room.objects.all())
    fallback_room = None
    fallback_created = False
    if not rooms:
        fallback_room, fallback_created = Room.objects.get_or_create(
            name="Room A", defaults={"room_type": "classroom"}
        )
        rooms = [fallback_room]

    requirements = []
    allocations = list(
        SubjectAllocation.objects.filter(
            klass__in=classes, periods_per_week__gt=0
        ).select_related("klass", "subject", "teacher")
    )
    for a in allocations:
        requirements.append(
            Requirement(
                klass=a.klass,
                subject=a.subject,
                teacher=a.teacher,
                periods_per_week=a.periods_per_week,
                requires_lab=a.requires_lab,
            )
        )

    availability = {}
    for row in TeacherAvailability.objects.filter(available=False).values("teacher_id", "weekday"):
        availability[(row["teacher_id"], str(row["weekday"]))] = False

    preferences = []
    for row in TeacherPreference.objects.select_related("teacher", "subject"):
        preferences.append(
            {
                "teacher_id": row.teacher_id,
                "subject_id": row.subject_id,
                "after_lunch": row.after_lunch,
            }
        )

    timetable, _ = Timetable.objects.get_or_create(
        name=timetable_name,
        academic_year=academic_year,
        term=term,
        defaults={"created_by": created_by, "status": TimetableStatus.DRAFT},
    )

    locked_entries = list(
        timetable.entries.filter(is_locked=True).select_related(
            "klass", "subject", "teacher", "room", "period"
        )
    )
    locked = [
        {
            "klass": e.klass,
            "weekday": e.weekday,
            "period": e.period,
            "subject": e.subject,
            "teacher": e.teacher,
            "room": e.room,
        }
        for e in locked_entries
    ]

    solver = Solver(
        classes=classes,
        days=days,
        periods=periods,
        requirements=requirements,
        rooms=rooms,
        locked=locked,
        availability=availability,
        preferences=preferences,
        max_time_seconds=max_seconds,
    )
    result = solver.solve()

    if result.satisfied:
        with transaction.atomic():
            timetable.entries.exclude(is_locked=True).delete()
            locked_keys = {
                (e.weekday, e.period_id, e.klass_id, e.section_id) for e in locked_entries
            }
            rows = []
            for a in result.assignments:
                key = (a["weekday"], a["period"].pk, a["klass"].pk, None)
                if key in locked_keys:
                    continue
                rows.append(
                    TimetableEntry(
                        timetable=timetable,
                        weekday=a["weekday"],
                        period=a["period"],
                        klass=a["klass"],
                        section=None,
                        subject=a["subject"],
                        teacher=a["teacher"],
                        room=a["room"],
                    )
                )
            TimetableEntry.objects.bulk_create(rows)

    timetable.constraints_summary = _build_summary(
        result,
        timetable,
        days=days,
        periods=periods,
        classes=classes,
        requirements=requirements,
        rooms=rooms,
        max_seconds=max_seconds,
        note=note,
        locked_preserved=len(locked_entries),
        fallback_created=fallback_created,
    )
    timetable.save(update_fields=["constraints_summary"])

    return {
        "timetable": timetable,
        "ok": result.satisfied,
        "status": result.status,
        "duration": time.perf_counter() - started,
        "solver_seconds": result.duration,
        "conflicts": result.soft_conflicts,
        "infeasible": result.infeasible_reasons,
        "entries": timetable.entries.count(),
    }


def _build_summary(result, timetable, days, periods, classes, requirements, rooms,
                   max_seconds, note, locked_preserved, fallback_created):
    teacher_gaps = _teacher_gaps(result.assignments, periods)
    total_slots = len(classes) * len(days) * len(periods)
    return {
        "generator": "ortools-cp-sat",
        "status": result.status,
        "satisfied": result.satisfied,
        "solver_seconds": round(result.duration, 3),
        "objective": result.objective,
        "classes": [c.name for c in classes],
        "classes_count": len(classes),
        "days": [dict(Weekday.choices)[d] for d in days],
        "periods_count": len(periods),
        "requirements_count": len(requirements),
        "teachers_count": len({r.teacher.pk for r in requirements}),
        "rooms_count": len(rooms),
        "entries_total": timetable.entries.count(),
        "locked_preserved": locked_preserved,
        "free_slots": max(0, total_slots - timetable.entries.count()),
        "gap_counts": {"teacher_idle_slots": teacher_gaps},
        "soft_conflicts": result.soft_conflicts,
        "infeasibility_reasons": result.infeasible_reasons,
        "fallback_room_created": fallback_created,
        "params": {
            "random_seed": 42,
            "max_time_seconds": max_seconds,
            "num_search_workers": 4,
            "consecutive_limit": 3,
        },
        "note": note,
        "generated_at": timezone.now().isoformat(),
    }


def _teacher_gaps(assignments, periods):
    by_teacher_day = defaultdict(list)
    for a in assignments:
        idx = next((i for i, p in enumerate(periods) if p.pk == a["period"].pk), None)
        if idx is None:
            continue
        by_teacher_day[(a["teacher"].pk, a["weekday"])].append(idx)

    gaps = 0
    for indexes in by_teacher_day.values():
        ordered = sorted(indexes)
        for prev, nxt in zip(ordered, ordered[1:]):
            gaps += max(0, nxt - prev - 1)
    return gaps


def conflicts_report(timetable):
    """Sanity check over existing entries: clashes and requirement deviations."""
    entries = list(
        timetable.entries.select_related(
            "klass", "section", "subject", "teacher", "room", "period"
        )
    )
    conflicts = []

    by_teacher = defaultdict(list)
    by_room = defaultdict(list)
    by_class = defaultdict(list)
    for e in entries:
        slot = (e.weekday, e.period_id)
        by_teacher[(e.teacher_id, *slot)].append(e)
        by_room[(e.room_id, *slot)].append(e)
        by_class[(e.klass_id, *slot)].append(e)

    for (_tid, weekday, _pid), group in by_teacher.items():
        if len(group) > 1:
            conflicts.append(
                {
                    "kind": "teacher",
                    "weekday": weekday,
                    "period": group[0].period,
                    "detail": (
                        f"{group[0].teacher} is scheduled in {len(group)} classes "
                        f"at the same time."
                    ),
                }
            )
    for (_rid, weekday, _pid), group in by_room.items():
        if len(group) > 1:
            conflicts.append(
                {
                    "kind": "room",
                    "weekday": weekday,
                    "period": group[0].period,
                    "detail": (
                        f"{group[0].room} is scheduled for {len(group)} classes "
                        f"at the same time."
                    ),
                }
            )
    for (_cid, weekday, _pid), group in by_class.items():
        if len(group) > 1:
            conflicts.append(
                {
                    "kind": "class",
                    "weekday": weekday,
                    "period": group[0].period,
                    "detail": (
                        f"{group[0].klass} has {len(group)} lessons at the same time."
                    ),
                }
            )

    required = {}
    for a in SubjectAllocation.objects.filter(periods_per_week__gt=0).select_related(
        "klass", "subject"
    ):
        required[(a.klass_id, a.subject_id)] = required.get(
            (a.klass_id, a.subject_id), 0
        ) + a.periods_per_week

    counts = Counter((e.klass_id, e.subject_id) for e in entries)
    klass_names = {c.pk: c.name for c in Class.objects.filter(pk__in=[k[0] for k in required])}
    subject_names = {
        s.pk: s.name
        for s in Subject.objects.filter(pk__in=[k[1] for k in required])
    }
    for (klass_id, subject_id), expected in required.items():
        actual = counts.get((klass_id, subject_id), 0)
        if actual != expected:
            conflicts.append(
                {
                    "kind": "requirement",
                    "weekday": "",
                    "period": None,
                    "detail": (
                        f"{klass_names.get(klass_id, klass_id)} / "
                        f"{subject_names.get(subject_id, subject_id)}: expected "
                        f"{expected} periods, found {actual}."
                    ),
                }
            )

    unavailable = {
        (row.teacher_id, str(row.weekday))
        for row in TeacherAvailability.objects.filter(available=False)
    }
    for e in entries:
        if (e.teacher_id, str(e.weekday)) in unavailable:
            conflicts.append(
                {
                    "kind": "availability",
                    "weekday": e.weekday,
                    "period": e.period,
                    "detail": (
                        f"{e.teacher} is marked unavailable on {e.get_weekday_display()}"
                        f" but has a lesson."
                    ),
                }
            )

    return conflicts