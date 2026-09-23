"""Deterministic offline timetable scheduler built on Google OR-Tools CP-SAT.

The solver takes the academic structure (classes, days, periods, subjects,
teachers, rooms, locked cells, teacher availability and preferences) and
returns a weekly assignment of (class, day, period) → (subject, teacher, room).

Hard constraints (spec §9):
    * exact weekly subject/teacher period counts per class
    * a class has at most one lesson per (day, period) slot
    * a teacher teaches at most one class per (day, period)
    * a room hosts at most one class per (day, period)
    * a teacher's unavailability per weekday is respected
    * already-locked cells are pinned

Soft constraints (penalised in the objective):
    * preferred subjects placed after lunch
    * teachers are not given long runs (> 3) of consecutive periods
"""

import time
from dataclasses import dataclass, field
from itertools import product

from ortools.sat.python import cp_model


class Requirement:
    """A weekly subject/teacher requirement for one class."""

    __slots__ = ("klass", "subject", "teacher", "periods_per_week", "requires_lab")

    def __init__(self, klass, subject, teacher, periods_per_week, requires_lab=False):
        self.klass = klass
        self.subject = subject
        self.teacher = teacher
        self.periods_per_week = periods_per_week
        self.requires_lab = requires_lab


@dataclass
class SolveResult:
    status: str
    satisfied: bool
    objective: float
    duration: float
    assignments: list = field(default_factory=list)
    soft_conflicts: list = field(default_factory=list)
    infeasible_reasons: list = field(default_factory=list)


class Solver:
    STATUS_OPTIMAL = "optimal"
    STATUS_FEASIBLE = "feasible"
    STATUS_INFEASIBLE = "infeasible"
    STATUS_TIMEOUT = "timeout"

    def __init__(
        self,
        *,
        classes,
        days,
        periods,
        requirements,
        rooms,
        locked=None,
        availability=None,
        preferences=None,
        blocked=None,
        max_time_seconds=30,
        random_seed=42,
        num_search_workers=4,
        consecutive_limit=3,
        after_lunch_weight=2,
        lunch_periods=None,
    ):
        self.classes = list(classes)
        self.days = list(days)
        self.periods = list(periods)
        self.requirements = list(requirements)
        self.rooms = list(rooms)
        self.locked = locked or []
        self.availability = availability or {}
        self.preferences = preferences or []
        self.blocked = blocked or []
        self.max_time_seconds = max_time_seconds
        self.random_seed = random_seed
        self.num_search_workers = num_search_workers
        self.consecutive_limit = consecutive_limit
        self.after_lunch_weight = after_lunch_weight
        self.lunch_periods = lunch_periods

        self._klass_index = {c.pk: i for i, c in enumerate(self.classes)}
        self._period_index = {p.pk: i for i, p in enumerate(self.periods)}
        self._day_index = {d: i for i, d in enumerate(self.days)}

        self._subjects = list({r.subject.pk: r.subject for r in self.requirements}.values())
        self._subject_index = {s.pk: i for i, s in enumerate(self._subjects)}
        self._teachers = list({r.teacher.pk: r.teacher for r in self.requirements}.values())
        self._teacher_index = {t.pk: i for i, t in enumerate(self._teachers)}
        self._room_index = {r.pk: i for i, r in enumerate(self.rooms)}

        self._lunch_set = self._build_lunch_set()
        self._pref = self._build_pref_map()

        # Candidate lessons per class index: list of (subject, teacher, room) indexes.
        lab_rooms = [r for r in self.rooms if "lab" in r.room_type.lower()]
        self._lessons = {}
        self._lesson_map = {}
        for k, klass in enumerate(self.classes):
            lessons = []
            for req in self.requirements:
                if req.klass.pk != klass.pk:
                    continue
                si = self._subject_index[req.subject.pk]
                ti = self._teacher_index[req.teacher.pk]
                room_choices = lab_rooms if (req.requires_lab and lab_rooms) else self.rooms
                for room in room_choices:
                    lessons.append((si, ti, self._room_index[room.pk]))
            lessons = list(dict.fromkeys(lessons))
            self._lessons[k] = lessons
            self._lesson_map[k] = {lesson: idx for idx, lesson in enumerate(lessons)}

        self._req_periods = {}
        for k, klass in enumerate(self.classes):
            counts = {}
            for req in self.requirements:
                if req.klass.pk != klass.pk:
                    continue
                si = self._subject_index[req.subject.pk]
                ti = self._teacher_index[req.teacher.pk]
                counts[(si, ti)] = counts.get((si, ti), 0) + req.periods_per_week
            self._req_periods[k] = counts

        self._lock_map = self._build_lock_map()
        self._blocked_map = self._build_blocked_map()
        self._assumptions = []

    def _build_lunch_set(self):
        if not self.periods:
            return set()
        if self.lunch_periods is not None:
            return {self._period_index[p.pk] for p in self.lunch_periods if p.pk in self._period_index}
        mid = len(self.periods) // 2
        return set(range(mid, len(self.periods)))

    def _build_pref_map(self):
        pref = {}
        for row in self.preferences:
            ti = self._teacher_index.get(row["teacher_id"])
            if ti is None:
                continue
            si = self._subject_index.get(row["subject_id"]) if row.get("subject_id") else None
            if "after_lunch" in row and row["after_lunch"]:
                pref.setdefault((ti, si), True)
        return pref

    def _build_lock_map(self):
        lock_items = []
        missing = []
        for item in self.locked:
            klass = item["klass"]
            if klass.pk not in self._klass_index or item["weekday"] not in self._day_index or item["period"].pk not in self._period_index:
                missing.append(f"Locked cell {klass} {item['weekday']} P{item['period'].order} is outside the scheduling grid")
                continue
            k = self._klass_index[klass.pk]
            d = self._day_index[item["weekday"]]
            p = self._period_index[item["period"].pk]
            si = self._subject_index.get(item["subject"].pk)
            ti = self._teacher_index.get(item["teacher"].pk)
            ri = self._room_index.get(item["room"].pk)
            lesson = (si, ti, ri)
            if None in lesson or lesson not in self._lesson_map[k]:
                missing.append(
                    f"Locked cell {klass} {item['weekday']} P{item['period'].order} "
                    f"cannot be represented by any subject allocation"
                )
                continue
            lock_items.append((k, d, p, self._lesson_map[k][lesson]))
        return {"items": lock_items, "missing": missing}

    def _build_blocked_map(self):
        """Occupied (day, period) slots that non-affecting classes already hold.

        A blocked slot forbids any assignment whose teacher *or* room is already
        booked there by a preserved out-of-scope class. This lets selective
        regeneration replace only the chosen classes/teachers/days while the
        solver still avoids double-booking against everything kept untouched.
        """
        blocked_teachers = {}
        blocked_rooms = {}
        for item in self.blocked:
            if item["weekday"] not in self._day_index or item["period"].pk not in self._period_index:
                continue
            slot = (item["weekday"], item["period"].pk)
            if item.get("teacher_id"):
                blocked_teachers.setdefault(slot, set()).add(item["teacher_id"])
            if item.get("room_id"):
                blocked_rooms.setdefault(slot, set()).add(item["room_id"])
        return {"teachers": blocked_teachers, "rooms": blocked_rooms}

    def solve(self):
        started = time.perf_counter()
        model, assumptions = self._build_model()

        if assumptions:
            model.AddAssumptions([var for var, _ in assumptions])

        solver = cp_model.CpSolver()
        solver.parameters.random_seed = self.random_seed
        solver.parameters.max_time_in_seconds = self.max_time_seconds
        solver.parameters.num_search_workers = self.num_search_workers
        status_code = solver.Solve(model)
        duration = time.perf_counter() - started

        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            assignments, soft = self._extract(solver)
            status = self.STATUS_OPTIMAL if status_code == cp_model.OPTIMAL else self.STATUS_FEASIBLE
            return SolveResult(
                status=status,
                satisfied=True,
                objective=solver.ObjectiveValue(),
                duration=duration,
                assignments=assignments,
                soft_conflicts=soft,
            )

        if status_code == cp_model.INFEASIBLE:
            reasons = self._infeasible_reasons(solver)
            if self._lock_map["missing"]:
                reasons = list(self._lock_map["missing"]) + reasons
            return SolveResult(
                status=self.STATUS_INFEASIBLE,
                satisfied=False,
                objective=0.0,
                duration=duration,
                infeasible_reasons=reasons,
            )

        return SolveResult(
            status=self.STATUS_TIMEOUT,
            satisfied=False,
            objective=0.0,
            duration=duration,
        )

    def _build_model(self):
        model = cp_model.CpModel()
        n_k, n_d, n_p = len(self.classes), len(self.days), len(self.periods)
        n_t = len(self._teachers)
        lessons = self._lessons

        x = {}
        y = {}
        for k in range(n_k):
            for d, p, l in product(range(n_d), range(n_p), range(len(lessons[k]))):
                x[(k, d, p, l)] = model.NewBoolVar(f"x_c{k}_d{d}_p{p}_l{l}")
        for ti, d, p in product(range(n_t), range(n_d), range(n_p)):
            y[(ti, d, p)] = model.NewBoolVar(f"y_t{ti}_d{d}_p{p}")

        self.x = x
        self.y = y

        assumptions = []
        self._assumptions = assumptions

        if not x:
            return model, assumptions

        assume_availability = model.NewBoolVar("assume_availability")
        assume_teacher_unique = model.NewBoolVar("assume_teacher_unique")
        assume_room_unique = model.NewBoolVar("assume_room_unique")
        assume_locked = model.NewBoolVar("assume_locked")
        assumptions.append((assume_availability, "Teacher availability constraints"))
        assumptions.append((assume_teacher_unique, "Teacher double-booking"))
        assumptions.append((assume_room_unique, "Room double-booking"))
        assumptions.append((assume_locked, "Locked cells conflict with the new schedule"))

        # Exact weekly subject/teacher period counts per class.
        for k, req_map in self._req_periods.items():
            for (si, ti), count in req_map.items():
                vars_ = [x[(k, d, p, l)] for d, p, l in product(
                    range(n_d), range(n_p),
                    [l for l, lesson in enumerate(lessons[k]) if lesson[0] == si and lesson[1] == ti],
                )]
                if not vars_:
                    continue
                asm = model.NewBoolVar(f"assume_req_k{k}_s{si}_t{ti}")
                subject = self._subjects[si]
                klass = self.classes[k]
                assumptions.append((asm, f"Subject {subject} in {klass}: exactly {count} periods cannot be scheduled"))
                model.Add(sum(vars_) == count).OnlyEnforceIf(asm)

        # At most one lesson per (class, day, period) slot.
        for k, d, p in product(range(n_k), range(n_d), range(n_p)):
            model.Add(sum(x[(k, d, p, l)] for l in range(len(lessons[k]))) <= 1)

        # Teacher books at most one class per (day, period).
        for ti, d, p in product(range(n_t), range(n_d), range(n_p)):
            vars_ = [
                x[(k, d, p, l)]
                for k in range(n_k)
                for l, lesson in enumerate(lessons[k])
                if lesson[1] == ti
            ]
            if not vars_:
                model.Add(y[(ti, d, p)] == 0)
                continue
            model.Add(sum(vars_) == y[(ti, d, p)])
            model.Add(y[(ti, d, p)] <= 1).OnlyEnforceIf(assume_teacher_unique)

        # Room hosts at most one class per (day, period).
        for ri, d, p in product(range(len(self.rooms)), range(n_d), range(n_p)):
            vars_ = [
                x[(k, d, p, l)]
                for k in range(n_k)
                for l, lesson in enumerate(lessons[k])
                if lesson[2] == ri
            ]
            if not vars_:
                continue
            model.Add(sum(vars_) <= 1).OnlyEnforceIf(assume_room_unique)

        # Respect teacher availability per weekday.
        for (k, d, p, l), var in x.items():
            si, ti, ri = lessons[k][l]
            teacher = self._teachers[ti]
            if self.availability.get((teacher.pk, str(self.days[d])), True) is False:
                model.Add(var == 0).OnlyEnforceIf(assume_availability)

        # Forbid slots already occupied by preserved out-of-scope classes
        # (teacher or room booked there on that day/period).
        blocked_teachers = self._blocked_map["teachers"]
        blocked_rooms = self._blocked_map["rooms"]
        if blocked_teachers or blocked_rooms:
            assume_blocked = model.NewBoolVar("assume_blocked")
            assumptions.append(
                (assume_blocked, "Preserved cells conflict with the new schedule")
            )
            for (k, d, p, l), var in x.items():
                si, ti, ri = lessons[k][l]
                slot = (self.days[d], self.periods[p].pk)
                if self._teachers[ti].pk in blocked_teachers.get(slot, set()):
                    model.Add(var == 0).OnlyEnforceIf(assume_blocked)
                elif self.rooms[ri].pk in blocked_rooms.get(slot, set()):
                    model.Add(var == 0).OnlyEnforceIf(assume_blocked)

        # Pin locked cells.
        for (k, d, p, l) in self._lock_map["items"]:
            model.Add(x[(k, d, p, l)] == 1).OnlyEnforceIf(assume_locked)

        # Soft objective: after-lunch preferences + consecutive-run avoidance.
        obj_terms = []
        for (k, d, p, l), var in x.items():
            si, ti, ri = lessons[k][l]
            if self._pref.get((ti, si), self._pref.get((ti, None), False)) and p not in self._lunch_set:
                obj_terms.append(self.after_lunch_weight * var)

        limit = self.consecutive_limit
        if limit > 0 and n_p > limit:
            for ti, d, p0 in product(range(n_t), range(n_d), range(n_p - limit)):
                window = [y[(ti, d, p0 + j)] for j in range(limit + 1)]
                pen = model.NewBoolVar(f"run_t{ti}_d{d}_p{p0}")
                model.AddBoolOr([w.Not() for w in window] + [pen])
                obj_terms.append(pen)

        if obj_terms:
            model.Minimize(sum(obj_terms))

        return model, assumptions

    def _extract(self, solver):
        assignments = []
        for (k, d, p, l), var in self.x.items():
            if solver.Value(var):
                si, ti, ri = self._lessons[k][l]
                assignments.append(
                    {
                        "klass": self.classes[k],
                        "weekday": self.days[d],
                        "period": self.periods[p],
                        "subject": self._subjects[si],
                        "teacher": self._teachers[ti],
                        "room": self.rooms[ri],
                    }
                )

        conflicts = []
        for a in assignments:
            si = self._subject_index[a["subject"].pk]
            ti = self._teacher_index[a["teacher"].pk]
            p = self._period_index[a["period"].pk]
            if self._pref.get((ti, si), self._pref.get((ti, None), False)) and p not in self._lunch_set:
                conflicts.append(
                    f"{a['teacher']} prefers {a['subject']} after lunch but got period {a['period']}"
                )

        limit = self.consecutive_limit
        if limit > 0:
            for ti, teacher in enumerate(self._teachers):
                for d, day in enumerate(self.days):
                    run = 0
                    longest = 0
                    for p in range(len(self.periods)):
                        if solver.Value(self.y[(ti, d, p)]):
                            run += 1
                            longest = max(longest, run)
                        else:
                            run = 0
                    if longest > limit:
                        conflicts.append(
                            f"{teacher} teaches {longest} consecutive periods on {day}"
                        )
        return assignments, conflicts

    def _infeasible_reasons(self, solver):
        core = solver.SufficientAssumptionsForInfeasibility()
        core_ids = {id(lit) for lit in core}
        reasons = [label for var, label in self._assumptions if id(var) in core_ids]
        if not reasons:
            reasons = ["No single constraint category can be relaxed to make the schedule feasible"]
        return reasons