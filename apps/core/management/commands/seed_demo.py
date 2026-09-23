"""Seed a believable, fully-linked demo dataset for marketing/product demo.

Non-destructive: designed to run against the demo database (demo.sqlite3)
produced by --settings project.settings.demo. Idempotent per run against a
fresh database; refuses to run on the dev/prod database by default (see
--force).

Covers: school profile, academic year/terms/periods/rooms, classes/sections/
subjects, staff+departments, houses, students, parents, attendance, fees,
finance, payroll, hardware, timetable (OR-Tools generator), communication
outbox, announcements + notifications.
"""

import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import SYSTEM_ROLES, Role, create_system_roles
from apps.academics.models import (
    AcademicLevel,
    Class,
    Period,
    Room,
    Section,
    Subject,
    SubjectAllocation,
)
from apps.attendance.models import StudentAttendance
from apps.communication.models import Channel, Outbox, OutboxStatus, MessageBatch, MessageTemplate
from apps.communication.services import enqueue_messages
from apps.accounts.models import User
from apps.fees.models import (
    Concession,
    FeeHead,
    FeePayment,
    FeeVoucher,
    FeeVoucherItem,
    PaymentMethod,
    StudentConcession,
)
from apps.finance.models import Expense, ExpenseCategory, Refund
from apps.hardware.models import (
    Device,
    DeviceEvent,
    DeviceStatus,
    DeviceType,
    MaintenanceRequest,
    TicketPriority,
    TicketStatus,
)
from apps.houses.models import House
from apps.hr.models import Department, Designation
from apps.notifications.models import Announcement, Audience, Notification
from apps.payroll.models import PayrollRun, SalaryComponent, ComponentKind
from apps.payroll.services import process_run
from apps.parents.models import Parent
from apps.school.models import AcademicYear, Holiday, SchoolProfile, Term, Weekday, WorkingDay
from apps.staff.models import Staff
from apps.students.models import Gender, Status, Student
from apps.timetable.models import TimetableStatus, Timetable
from apps.timetable.services import generate_timetable
from apps.communication.models import Priority


SCHOOL_NAME = "AlgoriSync Academy"

TEACHERS = {
    "Mathematics": ("Peter Maina", "T02"),
    "Science": ("Mary Wanjiku", "T03"),
    "English": ("Joseph Kiptoo", "T04"),
    "Kiswahili": ("Grace Achieng", "T05"),
    "Social Studies": ("David Otieno", "T06"),
    "CRE": ("Faith Njeri", "T07"),
    "Art & Craft": ("Samuel Mwangi", "T08"),
    "Music": ("Lucy Chebet", "T09"),
    "Physical Education": ("Lucy Chebet", "T09"),
}

STUDENTS = [
    ("Amani Ochieng", "M"),
    ("Baraka Wambui", "F"),
    ("Clara Akinyi", "F"),
    ("Daniel Mburu", "M"),
    ("Esther Njoki", "F"),
    ("Felix Odhiambo", "M"),
    ("Gloria Atieno", "F"),
    ("Hassan Yusuf", "M"),
    ("Imelda Nyambura", "F"),
    ("Josephine Koskei", "F"),
    ("Kevin Mwangi", "M"),
    ("Lilian Chepngetich", "F"),
    ("Martin Kilonzo", "M"),
    ("Nadia Hassan", "F"),
    ("Otieno Kemboi", "M"),
    ("Phyllis Wanjiru", "F"),
    ("Quinton Abdi", "M"),
    ("Ruth Namata", "F"),
    ("Samuel Rotich", "M"),
    ("Tabitha Jelagat", "F"),
    ("Titus Mumo", "M"),
    ("Ursula Mwikali", "F"),
    ("Victor Kamau", "M"),
    ("Winnie Jepkoech", "F"),
    ("Xavier Mwololo", "M"),
    ("Yvonne Owuor", "F"),
    ("Zahra Omar", "F"),
    ("Abigail Moraa", "F"),
    ("Brian Kibet", "M"),
    ("Cynthia Neema", "F"),
]


def _date(y, m, d):
    return date(y, m, d)


class Command(BaseCommand):
    help = "Seed a fully-linked demo dataset (run with --settings project.settings.demo)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Allow seeding the default dev/prod database.")

    @transaction.atomic
    def handle(self, *args, **opts):
        self.db_name = self._db_name()
        if "demo" not in self.db_name and not opts["force"]:
            raise CommandError(
                f"Refusing to seed database '{self.db_name}'. Seed demo data into the "
                f"demo database with --settings project.settings.demo (add --force to override)."
            )
        rng = random.Random(20260923)  # deterministic demo data
        self.rng = rng
        self.force = opts["force"]

        self.stdout.write(f"Seeding demo data into '{self.db_name}' ...")
        self._seed_identity()
        self._seed_academics_and_staff()
        self._seed_houses_students_parents()
        self._seed_system_data()
        self._seed_fees()
        self._seed_finance()
        self._seed_payroll()
        self._seed_hardware()
        self._seed_attendance()
        self._seed_timetable()
        self._seed_communication()
        self._seed_notifications()
        self.stdout.write(self.style.SUCCESS("DONE: demo dataset seeded."))

    # ------------------------------------------------------------------ utils
    def _db_name(self):
        from django.conf import settings
        opts = settings.DATABASES["default"].get("OPTIONS", {})
        name = opts.get("NAME") or settings.DATABASES["default"].get("NAME", "")
        return str(name)

    # ------------------------------------------------------------------ blocks
    def _seed_identity(self):
        admin = User.objects.create_superuser("admin", "admin@algorisync.co.ke", "admin123")
        admin.first_name = "System"
        admin.last_name = "Administrator"
        create_system_roles()
        admin.role = Role.objects.get(key="super_admin")
        admin.save()
        self.admin = admin

        if SchoolProfile.objects.exists():
            self.school = SchoolProfile.objects.first()
            self.school.name = SCHOOL_NAME
        else:
            self.school = SchoolProfile.objects.create(name=SCHOOL_NAME)
        self.school.tagline = "Knowledge. Discipline. Community."
        self.school.address = "Ogis Road, Industrial Area, Nakuru, Kenya"
        self.school.phone = "+254 700 123 456"
        self.school.email = "hello@algorisync.co.ke"
        self.school.website = "https://algorisync.co.ke"
        self.school.established_year = 1985
        self.school.bank_holder = "AlgoriSync Academy"
        self.school.bank_name = "Co-operative Bank"
        self.school.bank_branch = "Nakuru Town"
        self.school.bank_account_number = "01134567890123"
        self.school.bank_ifsc = "COOPKEKKXXX"
        self.school.save()

    def _seed_academics_and_staff(self):
        ay = AcademicYear.objects.create(
            name="2026/2027", start_date=_date(2026, 1, 5), end_date=_date(2026, 12, 18),
            is_active=True,
        )
        term3 = Term.objects.create(
            name="Term 3", academic_year=ay,
            start_date=_date(2026, 9, 1), end_date=_date(2026, 12, 18),
            is_active=True,
        )
        Term.objects.create(name="Term 1", academic_year=ay, start_date=_date(2026, 1, 5), end_date=_date(2026, 4, 3))
        Term.objects.create(name="Term 2", academic_year=ay, start_date=_date(2026, 5, 4), end_date=_date(2026, 8, 14))
        self.ay, self.term3 = ay, term3

        for wd in ["1", "2", "3", "4", "5"]:
            WorkingDay.objects.create(academic_year=ay, weekday=wd)
        Holiday.objects.create(academic_year=ay, name="Madaraka Day", start_date=_date(2026, 6, 1), end_date=_date(2026, 6, 1))
        Holiday.objects.create(academic_year=ay, name="Mashujaa Day", start_date=_date(2026, 10, 20), end_date=_date(2026, 10, 20))
        Holiday.objects.create(academic_year=ay, name="Jamhuri Day", start_date=_date(2026, 12, 12), end_date=_date(2026, 12, 12))

        periods_spec = [
            ("P1", "08:00", "08:40"), ("P2", "08:40", "09:20"),
            ("P3", "09:20", "10:00"), ("Break", "10:00", "10:30"),
            ("P4", "10:30", "11:10"), ("P5", "11:10", "11:50"),
            ("P6", "11:50", "12:30"), ("Lunch", "12:30", "13:10"),
            ("P7", "13:10", "13:50"), ("P8", "13:50", "14:30"),
        ]
        from datetime import datetime
        self.periods = {name: None for name, _, _ in periods_spec}
        for order, (name, st, en) in enumerate(periods_spec):
            self.periods[name] = Period.objects.create(
                name=name,
                start_time=datetime.strptime(st, "%H:%M").time(),
                end_time=datetime.strptime(en, "%H:%M").time(),
                order=order,
            )
        # Periods that should count as teaching slots for the solver grid.
        self.teaching_periods = [self.periods[n] for n in ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"]]

        self.rooms = []
        for idx in range(101, 109):
            self.rooms.append(Room.objects.create(name=f"Rm {idx}", capacity=40, room_type="classroom"))
        self.rooms.append(Room.objects.create(name="Science Lab 1", capacity=30, room_type="lab"))

        # Subjects
        subjects_spec = [
            ("English", "ENG"), ("Kiswahili", "KIS"), ("Mathematics", "MTH"),
            ("Science", "SCI"), ("Social Studies", "SST"), ("CRE", "CRE"),
            ("Art & Craft", "ART"), ("Music", "MUS"), ("Physical Education", "PHE"),
        ]
        self.subjects = {}
        for name, code in subjects_spec:
            self.subjects[name] = Subject.objects.create(name=name, code=code)

        # Departments, designations, staff
        deps = [
            ("Academic Department", "Deputy Head"),
            ("Finance Department", "Accounts Officer"),
            ("Administration", "Administration Officer"),
            ("ICT Department", "ICT Officer"),
            ("Library", "Librarian"),
        ]
        deps_map = {}
        for d, desig in deps:
            dep = Department.objects.create(name=d)
            deps_map[d] = (dep, desig)

        staff_spec = [
            ("T01", "Jane", "Aloo", "female", "Academic Department", "Deputy Head", False, 85000),
            ("T02", "Peter", "Maina", "male", "Academic Department", "Senior Teacher, Mathematics", True, 52000),
            ("T03", "Mary", "Wanjiku", "female", "Academic Department", "Teacher, Science", True, 48000),
            ("T04", "Joseph", "Kiptoo", "male", "Academic Department", "Teacher, English", True, 47000),
            ("T05", "Grace", "Achieng", "female", "Academic Department", "Teacher, Kiswahili", True, 46000),
            ("T06", "David", "Otieno", "male", "Academic Department", "Teacher, Social Studies", True, 45000),
            ("T07", "Faith", "Njeri", "female", "Academic Department", "Teacher, CRE", True, 45000),
            ("T08", "Samuel", "Mwangi", "male", "Academic Department", "Teacher, Art & Craft", True, 44000),
            ("T09", "Lucy", "Chebet", "female", "Academic Department", "Teacher, Music & PE", True, 43000),
            ("T10", "Robert", "Karanja", "male", "Finance Department", "Accounts Officer", False, 38000),
            ("T11", "Caroline", "Njoroge", "female", "Library", "Librarian", False, 35000),
            ("T12", "Brian", "Omondi", "male", "ICT Department", "ICT Officer", False, 40000),
        ]
        self.staff_map = {}
        self.teachers = []
        for code, fn, ln, gender, dep_name, desig, is_teacher, salary in staff_spec:
            dep, _ = deps_map[dep_name]
            st = Staff.objects.create(
                employee_code=code, first_name=fn, last_name=ln, gender=gender,
                department=dep, designation=desig, is_teacher=is_teacher,
                joining_date=_date(2020 + self.rng.randrange(0, 5), self.rng.randrange(1, 13) or 1, 2),
                salary=salary,
            )
            self.staff_map[code] = st
            if is_teacher:
                self.teachers.append(st)

        # Teacher users
        for i, st in enumerate(self.teachers[:3]):
            User.objects.create_user(
                f"staff{i + 1}", f"staff{i + 1}@example.com", f"staff{i + 1}123",
                first_name=st.first_name, last_name=st.last_name, staff=st,
            )

        # Classes & sections
        levels = [
            ("Pre-Primary 1", AcademicLevel.PRE_PRIMARY),
            ("Pre-Primary 2", AcademicLevel.PRE_PRIMARY),
            ("Grade 1", AcademicLevel.PRIMARY),
            ("Grade 2", AcademicLevel.PRIMARY),
            ("Grade 3", AcademicLevel.PRIMARY),
            ("Grade 4", AcademicLevel.PRIMARY),
            ("Grade 5", AcademicLevel.PRIMARY),
            ("Grade 6", AcademicLevel.PRIMARY),
        ]
        self.classes = {}
        self.sections = {}
        for i, (cname, lvl) in enumerate(levels):
            ct = Class.objects.create(name=cname, level=lvl, class_teacher=self.teachers[i % len(self.teachers)])
            ct.subjects.set(self.subjects.values())
            self.classes[cname] = ct
            sections = ["A", "B"] if cname not in ("Pre-Primary 1", "Pre-Primary 2") else ["A"]
            self.sections[cname] = []
            for si, sname in enumerate(sections):
                sec = Section.objects.create(
                    klass=ct, name=sname, room=self.rooms[i % len(self.rooms)]
                )
                self.sections[cname].append(sec)
        self.class_names = list(self.classes.keys())

    def _seed_houses_students_parents(self):
        houses = [
            ("Red House", "Red"), ("Blue House", "Blue"),
            ("Green House", "Green"), ("Yellow House", "Yellow"),
        ]
        self.houses = []
        for name, _ in houses:
            self.houses.append(House.objects.create(name=name))

        # Distribute students across classes/sections.
        placement = []
        for cn in self.class_names:
            secs = self.sections[cn]
            count = 4 if len(secs) == 1 else 2 if len(secs) == 2 else 3
            for sec in secs:
                for _ in range(count):
                    placement.append((cn, sec))
        # Pad/trim to list length deterministically.
        placement = (placement * ((len(STUDENTS) // len(placement)) + 1))[: len(STUDENTS)]
        self.students = []
        for i, (name, gender) in enumerate(STUDENTS):
            first, last = name.split(" ", 1)
            cn, sec = placement[i]
            self.students.append(Student.objects.create(
                admission_number=f"ADM/2026/{i + 1:04d}",
                first_name=first, last_name=last,
                gender=Gender.MALE if gender == "M" else Gender.FEMALE,
                klass=self.classes[cn], section=sec, house=self.houses[i % len(self.houses)],
                date_of_birth=_date(2013 + (i % 5), (i % 12) + 1, (i % 27) + 1),
                status=Status.ACTIVE,
                medical_notes="None" if i % 11 else "Asthma (inhaler on file)",
            ))

        # Parents / guardians
        guardian_surnames = [
            ("James Ochieng"), ("Catherine Wambui"), ("Samson Mburu"), ("Joyce Akinyi"),
            ("Paul Njoki"), ("Mary Atieno"), ("John Yusuf"), ("Agnes Nyambura"),
            ("Meshack Koskei"), ("Diana Mwangi"), ("Peter Kilonzo"), ("Halima Hassan"),
            ("Elijah Kemboi"), ("Susan Wanjiru"), ("Ahmed Abdi"), ("Rose Namata"),
            ("Fred Rotich"), ("Zipporah Jelagat"), ("Kevin Mumo"), ("Lydia Mwikali"),
            ("George Kamau"), ("Esther Jepkoech"), ("Donald Mwololo"), ("Mercy Owuor"),
            ("Omar Hussein"),
        ]
        rng = self.rng
        self.parents = []
        for i, std in enumerate(self.students):
            gname = guardian_surnames[i % len(guardian_surnames)]
            rel = "Father" if (i + rng.randrange(2)) % 2 == 0 else "Mother"
            phone = f"+2547{rng.randrange(100, 999)}{rng.randrange(1000, 9999)}"
            parent, created = Parent.objects.get_or_create(
                first_name=gname.split()[0], last_name=gname.split()[1],
                defaults={
                    "relationship": rel, "occupation": rng.choice(
                        ["Farmer", "Teacher", "Business", "Nurse", "Engineer", "Driver", "Clerk"]
                    ),
                    "phone": phone, "whatsapp_number": phone,
                    "email": f"{gname.split()[0].lower()}.{gname.split()[1].lower()}@example.com",
                    "address": "Nakuru County, Kenya",
                    "emergency_contact": f"+2547{rng.randrange(100, 999)}{rng.randrange(1000, 9999)}",
                },
            )
            parent.students.add(std)
            self.parents.append(parent)

        # Parent portal account for demo (guardian of a Grade 1 pupil).
        if not User.objects.filter(username="parent1").exists():
            demo_parent = self.parents[0]
            pc = demo_parent.students.first()
            User.objects.create_user(
                "parent1", "guardian.one@example.com", "parent123",
                first_name=demo_parent.first_name,
                last_name=demo_parent.last_name, parent_profile=demo_parent,
            )

        # House captains
        for h, (name, _) in zip(self.houses, houses):
            h.captain = self.students[h.id % len(self.students)]
            h.vice_captain = self.students[(h.id + 5) % len(self.students)]
            h.save()

    def _seed_system_data(self):
        """Fee heads, expense categories present before their transactions."""
        self.fee_heads = {}
        for name, amt in [
            ("Tuition Fee", None), ("Transport Fee", None), ("Lunch Fee", None), ("Activity Fee", None),
        ]:
            head = FeeHead.objects.create(name=name, amount=0)
            self.fee_heads[name] = head
        self.fee_amounts = {"Tuition Fee": 9000, "Transport Fee": 4500, "Lunch Fee": 3000, "Activity Fee": 1500}
        self.fee_heads["Tuition Fee"].amount = 9000
        self.fee_heads["Transport Fee"].amount = 4500
        self.fee_heads["Lunch Fee"].amount = 3000
        self.fee_heads["Activity Fee"].amount = 1500
        for head in self.fee_heads.values():
            head.save()

        Scholarship10 = Concession.objects.create(
            name="Academic Excellence 10%", percentage=10, flat_amount=None,
        )
        Scholarship10.fee_heads.set([])
        for i, std in enumerate(self.students):
            if i % 11 == 0:
                StudentConcession.objects.create(concession=Scholarship10, student=std)

    def _seed_fees(self):
        rng = self.rng
        admin = self.admin
        for i, std in enumerate(self.students):
            voucher = FeeVoucher.objects.create(
                student=std, due_date=_date(2026, 9, 30), created_by=admin,
            )
            for name, amt in self.fee_amounts.items():
                head = self.fee_heads[name]
                base = rng.choice([amt, amt])
                discount = 0
                if i % 11 == 0:
                    discount = round(head.amount * 0.10, 2)
                FeeVoucherItem.objects.create(
                    voucher=voucher, fee_head=head, amount=base, discount=discount,
                )
            if i % 10 == 3:
                voucher.status = "issued"
            elif i % 23 == 5:
                voucher.status = "cancelled"
            else:
                voucher.status = "issued"
            voucher.save()
        # Collect payments for most vouchers (some partial).
        for i, std in enumerate(self.students):
            if i % 8 == 7:
                continue
            voucher = std.vouchers.filter(status="issued").first()
            if not voucher:
                voucher = std.vouchers.order_by("due_date").first()
            if not voucher:
                continue
            total = sum(it.amount - it.discount for it in voucher.items.all())
            paid = total if i % 6 else total / 2
            FeePayment.objects.create(
                student=std, fee_head=self.fee_heads["Tuition Fee"], amount=paid,
                paid_on=_date(2026, 9, 2 + (i % 20)),
                method=rng.choice(["cash", "bank", "card", "online"]),
                received_by=admin,
            )

    def _seed_finance(self):
        admin = self.admin
        cats = {}
        for name in ["Utilities", "Repairs & Maintenance", "Stationery", "Staff Welfare", "Security", "Transport"]:
            cats[name] = ExpenseCategory.objects.create(name=name)
        expenses = [
            ("Electricity bill", "Utilities", 14850, _date(2026, 9, 8)),
            ("Water bill", "Utilities", 6240, _date(2026, 9, 12)),
            ("Laptop charger replacement", "Repairs & Maintenance", 2300, _date(2026, 9, 2)),
            ("Classroom fan cleaning", "Repairs & Maintenance", 4000, _date(2026, 9, 15)),
            ("Printer toner (4x)", "Stationery", 9200, _date(2026, 9, 5)),
            ("Exercise books (class bundles)", "Stationery", 18000, _date(2026, 9, 18)),
            ("Staff birthday cakes", "Staff Welfare", 6800, _date(2026, 9, 10)),
            ("Medicare reimbursement", "Staff Welfare", 3500, _date(2026, 9, 20)),
            ("Night guard stipend", "Security", 4500, _date(2026, 9, 6)),
            ("School bus fuel", "Transport", 12600, _date(2026, 9, 16)),
        ]
        for title, cat, amt, d in expenses:
            Expense.objects.create(
                title=title, category=cats[cat], amount=amt, expense_date=d,
                method=self.rng.choice(["cash", "bank", "card"]), recorded_by=admin,
            )
        Refund.objects.create(
            student=self.students[5], amount=900, refund_date=_date(2026, 9, 14),
            reason="Overpayment on Term 3 tuition", method="bank", recorded_by=admin,
        )
        Refund.objects.create(
            student=self.students[18], amount=1350, refund_date=_date(2026, 9, 11),
            reason="Cancelled transport for Term 3", method="cash", recorded_by=admin,
        )

    def _seed_payroll(self):
        comps = [
            ("House Allowance", "allowance", 8000, None, "all"),
            ("Transport Allowance", "allowance", 5000, None, "all"),
            ("Medical Allowance", "allowance", 2000, None, "all"),
            ("Hardship Allowance", "allowance", 3000, None, "teacher"),
            ("Uniform Allowance", "allowance", 1500, None, "non_teaching"),
            ("NHIF Deduction", "deduction", 500, None, "all"),
            ("NSSF Deduction", "deduction", 700, None, "all"),
        ]
        for name, kind, amt, pct, applies in comps:
            SalaryComponent.objects.create(
                name=name, kind=kind, amount=amt, percentage=pct,
                applies_to=applies,
            )
        run = PayrollRun.objects.create(month=9, year=2026)
        run.created_by = self.admin
        run.save()
        self.run = run
        try:
            n = process_run(run)
            self.stdout.write(f"  Payroll: processed {n} pay slips for {run.title}")
        except Exception as exc:  # pragma: no cover - defensive
            self.stdout.write(self.style.WARNING(f"  Payroll process_run skipped: {exc}"))

    def _seed_hardware(self):
        admin = self.admin
        devices = [
            ("Android SMS Gateway 01", DeviceType.GATEWAY, DeviceStatus.ACTIVE, "usb"),
            ("HP LaserJet M110w", DeviceType.PRINTER, DeviceStatus.ACTIVE, "wlan"),
            ("Canon Lide 300 Scanner", DeviceType.SCANNER, DeviceStatus.ACTIVE, "usb"),
            ("Biometric Reader F60", DeviceType.BIOMETRIC, DeviceStatus.ACTIVE, "usb"),
            ("Epson EB-2042 Projector", DeviceType.PROJECTOR, DeviceStatus.MAINTENANCE, "lan"),
            ("Admin Desktop CF-01", DeviceType.DESKTOP, DeviceStatus.ACTIVE, "lan"),
        ]
        self.devices = []
        for name, dtype, status, conn in devices:
            dev = Device.objects.create(name=name, device_type=dtype, status=status, connection=conn)
            self.devices.append(dev)
            DeviceEvent.objects.create(device=dev, event_type="registered", detail="Device registered during setup")
        gw = self.devices[0]
        for ev in [
            ("heartbeat", "Gateway heartbeat received"),
            ("sms_sent", "SMS batch delivered via local gateway"),
            ("heartbeat", "Gateway heartbeat received"),
        ]:
            DeviceEvent.objects.create(device=gw, event_type=ev[0], detail=ev[1])
        tickets = [
            (self.devices[4], "Projector lamp flickers", TicketPriority.HIGH, TicketStatus.IN_PROGRESS),
            (self.devices[0], "SIM reboots gateway weekly", TicketPriority.MEDIUM, TicketStatus.OPEN),
            (self.devices[1], "Paper tray needs cleaning", TicketPriority.LOW, TicketStatus.RESOLVED),
        ]
        for dev, title, prio, status in tickets:
            MaintenanceRequest.objects.create(
                device=dev, issue_title=title, description=title + ". Investigated by ICT.",
                priority=prio, status=status, reported_by=admin,
            )

    def _seed_attendance(self):
        admin = self.admin
        days = [_date(2026, 9, 21), _date(2026, 9, 22), _date(2026, 9, 23)]
        for d in days:
            for i, std in enumerate(self.students):
                roll = i % 15
                if roll == 7:
                    st = "absent"
                elif roll == 9:
                    st = "late"
                elif roll == 12:
                    st = "excused"
                else:
                    st = "present"
                StudentAttendance.objects.create(
                    student=std, date=d, status=st, recorded_by=admin,
                )

    def _seed_timetable(self):
        periods_pw = {
            "English": 4, "Kiswahili": 4, "Mathematics": 4, "Science": 4,
            "Social Studies": 3, "CRE": 2, "Art & Craft": 2, "Music": 2, "Physical Education": 2,
        }
        core_of = {
            "Pre-Primary 1": ["English", "Kiswahili", "Mathematics", "CRE", "Music", "Physical Education"],
            "Pre-Primary 2": ["English", "Kiswahili", "Mathematics", "CRE", "Music", "Physical Education"],
            "Grade 1": ["English", "Kiswahili", "Mathematics", "Science", "CRE", "Art & Craft", "Music", "Physical Education"],
            "Grade 2": ["English", "Kiswahili", "Mathematics", "Science", "CRE", "Art & Craft", "Music", "Physical Education"],
            "Grade 3": ["English", "Kiswahili", "Mathematics", "Science", "Social Studies", "CRE", "Art & Craft", "Music", "Physical Education"],
            "Grade 4": list(periods_pw),
            "Grade 5": list(periods_pw),
            "Grade 6": list(periods_pw),
        }
        for cn in self.class_names:
            for subj_name in core_of[cn]:
                teacher = self.teacher_for(subj_name)
                SubjectAllocation.objects.create(
                    klass=self.classes[cn], section=None, subject=self.subjects[subj_name],
                    teacher=teacher, periods_per_week=periods_pw[subj_name],
                )
        self.stdout.write("  Timetable: solving with OR-Tools (max 45 s, manual fallback)...")
        tt = None
        try:
            result = generate_timetable(
                "Term 3 Master Timetable",
                self.ay, self.term3,
                classes=[self.classes[cn] for cn in self.class_names],
                max_seconds=45,
                note="Term 3 timetable",
                created_by=self.admin,
            )
            cand = result.get("timetable")
            entries = result.get("entries") or []
            if cand and len(entries) > 50:
                tt = cand
                self.stdout.write(
                    f"  Timetable: {result.get('status')} | entries={len(entries)} "
                    f"| conflicts={len(result.get('conflicts') or [])}"
                )
        except Exception as exc:  # pragma: no cover - defensive
            self.stdout.write(self.style.WARNING(f"  Timetable generator skipped: {exc}"))
        if tt is None:
            tt = Timetable.objects.create(
                name="Term 3 Master Timetable", academic_year=self.ay, term=self.term3,
                status=TimetableStatus.DRAFT, created_by=self.admin,
            )
            self._fill_timetable_manually(tt)
            self.stdout.write(f"  Timetable: manual deterministic fill, entries={tt.entries.count()}")
        tt.status = TimetableStatus.PUBLISHED
        tt.save(update_fields=["status"])

    def _fill_timetable_manually(self, tt):
        """Deterministic, conflict-free weekly grid: rotate subjects per class."""
        seq = {
            "Pre-Primary 1": ["English", "Mathematics", "Kiswahili", "CRE", "Music", "Physical Education", "English", "Mathematics"],
            "Pre-Primary 2": ["Mathematics", "English", "Kiswahili", "CRE", "Music", "Physical Education", "Mathematics", "English"],
            "Grade 1": ["English", "Mathematics", "Kiswahili", "Science", "CRE", "Art & Craft", "Music", "Physical Education"],
            "Grade 2": ["Mathematics", "English", "Kiswahili", "Science", "CRE", "Art & Craft", "Music", "Physical Education"],
            "Grade 3": ["English", "Mathematics", "Kiswahili", "Science", "Social Studies", "CRE", "Art & Craft", "Physical Education"],
            "Grade 4": ["Mathematics", "English", "Kiswahili", "Science", "Social Studies", "CRE", "Art & Craft", "Physical Education"],
            "Grade 5": ["English", "Mathematics", "Kiswahili", "Science", "Social Studies", "CRE", "Art & Craft", "Physical Education"],
            "Grade 6": ["Mathematics", "English", "Kiswahili", "Science", "Social Studies", "CRE", "Art & Craft", "Physical Education"],
        }
        lab = next((r for r in self.rooms if r.name.startswith("Science Lab")), self.rooms[0])
        for cidx, cn in enumerate(self.class_names):
            room = self.rooms[cidx % len(self.rooms)]
            pattern = seq[cn]
            for weekday in ["1", "2", "3", "4", "5"]:
                day_idx = int(weekday) - 1
                for pidx, period in enumerate(self.teaching_periods):
                    subject_name = pattern[(pidx + day_idx * 2 + cidx) % len(pattern)]
                    subject = self.subjects[subject_name]
                    teacher = self.teacher_for(subject_name)
                    from apps.timetable.models import TimetableEntry
                    TimetableEntry.objects.create(
                        timetable=tt, weekday=weekday, period=period, klass=self.classes[cn],
                        subject=subject, teacher=teacher,
                        room=lab if subject_name == "Science" else room,
                    )

    def teacher_for(self, subject_name):
        _, code = TEACHERS[subject_name]
        return self.staff_map[code]

    def _seed_communication(self):
        tpl = MessageTemplate.objects.create(
            key="fee_reminder", name="Term Fee Reminder",
            body="Dear {parent_name}, please note the Term 3 fee balance for "
                 "{student_name} ({class_name}) is due by {date}. — {school_name}",
            is_system=True,
        )
        batch = MessageBatch.objects.create(
            subject="Term 3 Fee Reminders", channel=Channel.SMS, created_by=self.admin,
        )
        recipients, body = [], "Dear Parent, kindly clear your ward's Term 3 fee balance by 30 Sep. — AlgoriSync Academy"
        from apps.communication.services import recipient_for_parent
        recipient_list = []
        for s in self.students[:10]:
            p = s.guardians.first()
            if p and p.phone:
                recipient_list.append(recipient_for_parent(p, s))
        enqueue_messages(
            recipients=recipient_list,
            body_text=body, template=tpl, channel=Channel.SMS, priority=Priority.NORMAL,
            batch=batch,
        )
        # Some already-delivered and one failed (offline retry demo).
        p1 = self.students[0].guardians.first()
        Outbox.objects.create(
            batch=batch, template=tpl, recipient=p1.phone or "07xxxxxxxx",
            to_number=p1.phone, channel=Channel.SMS, priority=Priority.HIGH,
            message="Dear Parent, fee balance reminder. — AlgoriSync Academy", body="",
            status=OutboxStatus.SENT, attempt_count=1,
        )
        p2 = self.students[1].guardians.first()
        Outbox.objects.create(
            batch=batch, template=tpl, recipient=p2.phone or "07xxxxxxxx",
            to_number=p2.phone, channel=Channel.SMS, priority=Priority.NORMAL,
            message="Dear Parent, fee balance reminder. — AlgoriSync Academy", body="",
            status=OutboxStatus.FAILED, attempt_count=3,
        )

    def _seed_notifications(self):
        ann1 = Announcement.objects.create(
            title="Inter-House Athletics Day — Friday 2pm",
            message="All students report to the sports field at 13:45. Houses compete in relays, "
                    "sprints and long jump. Parents welcome.",
            audience=Audience.ALL, is_emergency=False, created_by=self.admin,
        )
        ann2 = Announcement.objects.create(
            title="Power shutdown Saturday 9-11am",
            message="Maintenance works on the local grid. Systems and projectors will be offline. "
                    "Timelines continue as scheduled.",
            audience=Audience.STAFF, is_emergency=True, created_by=self.admin,
        )
        Notification.objects.create(recipient=self.admin, announcement=ann1, text=ann1.title)
        Notification.objects.create(recipient=self.admin, announcement=ann2, text=ann2.title)
        Notification.objects.create(
            recipient=self.admin,
            text="Fee reminder: 18 full-term balances due by 30 Sep",
        )
        Notification.objects.create(
            recipient=self.admin,
            text="Gateway: 42 SMS delivered in the last 24h",
        )