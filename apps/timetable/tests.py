"""Tests for timetable services & model cell-swapping (spec §9)."""

from datetime import date

from django.core.management import call_command
from django.test import TestCase

from apps.academics.models import Class, Period, Room, Subject, SubjectAllocation
from apps.school.models import AcademicYear, Weekday, WorkingDay
from apps.staff.models import Staff
from apps.students.models import Status

from .models import Timetable, TimetableEntry
from .services import _working_weekdays, conflicts_report, regenerate_timetable


class WorkingWeekdaysTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.year = AcademicYear.objects.create(
            name="2026/2027", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
        )

    def test_defaults_to_monday_friday_when_no_custom_days(self):
        self.assertEqual(_working_weekdays(None), ["1", "2", "3", "4", "5"])

    def test_respects_configured_working_days(self):
        WorkingDay.objects.create(academic_year=self.year, weekday=Weekday.MONDAY)
        WorkingDay.objects.create(academic_year=self.year, weekday=Weekday.TUESDAY)
        days = _working_weekdays(self.year)
        self.assertEqual(days, ["1", "2"])

    def test_ignores_invalid_weekday_codes(self):
        WorkingDay.objects.create(academic_year=self.year, weekday="9")
        self.assertEqual(_working_weekdays(self.year), ["1", "2", "3", "4", "5"])


class EntrySwapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.year = AcademicYear.objects.create(
            name="2026/2027", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
        )
        cls.room = Room.objects.create(name="Room T1")
        cls.period1 = Period.objects.create(
            name="P1", start_time="08:00", end_time="08:45", order=1
        )
        cls.period2 = Period.objects.create(
            name="P2", start_time="08:45", end_time="09:30", order=2
        )
        cls.klass = Class.objects.create(name="Timetable A")
        cls.klass2 = Class.objects.create(name="Timetable B")
        cls.subject = Subject.objects.create(name="Maths T")
        cls.teacher = Staff.objects.create(
            employee_code="T-SW", first_name="Swap", last_name="Teacher",
            is_teacher=True, status=Status.ACTIVE,
        )
        cls.teacher2 = Staff.objects.create(
            employee_code="T-SW2", first_name="Other", last_name="Teacher",
            is_teacher=True, status=Status.ACTIVE,
        )
        cls.tt = Timetable.objects.create(name="SWAP-TT", academic_year=cls.year)

    def _entry(self, klass, period, weekday, teacher):
        return TimetableEntry.objects.create(
            timetable=self.tt, weekday=weekday, period=period,
            klass=klass, subject=self.subject, teacher=teacher, room=self.room,
        )

    def test_swap_two_cells(self):
        a = self._entry(self.klass, self.period1, Weekday.MONDAY, self.teacher)
        b = self._entry(self.klass, self.period2, Weekday.MONDAY, self.teacher)
        a.swap_with(b)
        a.refresh_from_db()
        b.refresh_from_db()
        # a now sits in B's old slot and vice versa.
        self.assertEqual(a.weekday, Weekday.MONDAY)
        self.assertEqual(b.weekday, Weekday.MONDAY)
        self.assertEqual(a.period_id, self.period2.pk)
        self.assertEqual(b.period_id, self.period1.pk)

    def test_swap_respects_unique_cell_constraint(self):
        a = self._entry(self.klass, self.period1, Weekday.MONDAY, self.teacher)
        b = self._entry(self.klass2, self.period1, Weekday.MONDAY, self.teacher2)
        a.swap_with(b)
        a.refresh_from_db()
        b.refresh_from_db()
        # Different classes in the same slot: swapping (weekday, period)
        # coordinates is a no-op and must not violate the unique cell rule.
        self.assertEqual(a.period_id, self.period1.pk)
        self.assertEqual(b.period_id, self.period1.pk)
        self.assertEqual(a.klass_id, self.klass.pk)
        self.assertEqual(b.klass_id, self.klass2.pk)


class ConflictsReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.year = AcademicYear.objects.create(
            name="2026/2027", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
        )
        cls.room = Room.objects.create(name="Room C1")
        cls.p1 = Period.objects.create(
            name="P1", start_time="08:00", end_time="08:45", order=1
        )
        cls.p2 = Period.objects.create(
            name="P2", start_time="08:45", end_time="09:30", order=2
        )
        cls.k1 = Class.objects.create(name="C-A")
        cls.k2 = Class.objects.create(name="C-B")
        cls.s1 = Subject.objects.create(name="S-A")
        cls.s2 = Subject.objects.create(name="S-B")
        cls.t = Staff.objects.create(
            employee_code="T-CF", first_name="C", last_name="F", is_teacher=True,
            status=Status.ACTIVE,
        )
        cls.tt = Timetable.objects.create(name="CF-TT", academic_year=cls.year)

    def test_empty_timetable_has_no_conflicts(self):
        self.assertEqual(conflicts_report(self.tt), [])

    def test_teacher_clash_is_reported(self):
        TimetableEntry.objects.create(
            timetable=self.tt, weekday=Weekday.MONDAY, period=self.p1,
            klass=self.k1, subject=self.s1, teacher=self.t, room=self.room,
        )
        TimetableEntry.objects.create(
            timetable=self.tt, weekday=Weekday.MONDAY, period=self.p1,
            klass=self.k2, subject=self.s2, teacher=self.t, room=self.room,
        )
        conflicts = conflicts_report(self.tt)
        self.assertTrue(any(c["kind"] == "teacher" for c in conflicts))

    def test_requirement_deviation_is_reported(self):
        SubjectAllocation.objects.create(
            klass=self.k1, subject=self.s1, teacher=self.t, periods_per_week=2
        )
        TimetableEntry.objects.create(
            timetable=self.tt, weekday=Weekday.MONDAY, period=self.p1,
            klass=self.k1, subject=self.s1, teacher=self.t, room=self.room,
        )
        conflicts = conflicts_report(self.tt)
        self.assertTrue(any(c["kind"] == "requirement" for c in conflicts))


class RegenerateNoopTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.year = AcademicYear.objects.create(
            name="2026/2027", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
        )
        cls.room = Room.objects.create(name="Room R1")
        cls.p1 = Period.objects.create(
            name="P1", start_time="08:00", end_time="08:45", order=1
        )
        cls.k1 = Class.objects.create(name="R-A")
        cls.s1 = Subject.objects.create(name="R-S")
        cls.t = Staff.objects.create(
            employee_code="T-RG", first_name="Regen", last_name="Teacher",
            is_teacher=True, status=Status.ACTIVE,
        )
        cls.tt = Timetable.objects.create(name="RG-TT", academic_year=cls.year)

    def test_regenerate_without_scoped_entries_is_noop(self):
        TimetableEntry.objects.create(
            timetable=self.tt, weekday=Weekday.MONDAY, period=self.p1,
            klass=self.k1, subject=self.s1, teacher=self.t, room=self.room,
        )
        res = regenerate_timetable(self.tt, classes=[], max_seconds=5)
        self.assertEqual(res["status"], "noop")
        self.assertTrue(res["ok"])
        self.assertEqual(res["rebuilt"], 0)