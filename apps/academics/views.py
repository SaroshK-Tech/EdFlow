from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.students.models import Student

from .forms import (
    ClassForm,
    HomeworkForm,
    RoomForm,
    SectionForm,
    SubjectForm,
    SubmissionForm,
    SubmissionGradeForm,
    SyllabusForm,
)
from .models import (
    Class,
    Homework,
    Room,
    Section,
    Subject,
    Submission,
    SubmissionStatus,
    Syllabus,
)


class ClassListView(EdFlowMixin, SearchMixin, ListView):
    model = Class
    template_name = "academics/class_list.html"
    context_object_name = "classes"
    page_title = "Classes"
    page_subtitle = "Grades, sections and their subjects"
    active_page = "academics"
    search_fields = ["name"]
    search_placeholder = "Search classes…"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.annotate(student_count=Count("students", distinct=True))


class ClassCreateView(EdFlowMixin, CreateView):
    model = Class
    form_class = ClassForm
    template_name = "academics/class_form.html"
    page_title = "Add Class"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"class.create {self.object.name}")
        messages.success(self.request, f"Class {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:classes")


class ClassUpdateView(EdFlowMixin, UpdateView):
    model = Class
    form_class = ClassForm
    template_name = "academics/class_form.html"
    context_object_name = "klass"
    page_title = "Edit Class"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Class updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:classes")


class SectionListView(EdFlowMixin, SearchMixin, ListView):
    model = Section
    template_name = "academics/section_list.html"
    context_object_name = "sections"
    page_title = "Sections"
    page_subtitle = "Class divisions and assigned rooms"
    active_page = "academics"
    search_fields = ["klass__name", "name"]
    search_placeholder = "Search sections…"


class SectionCreateView(EdFlowMixin, CreateView):
    model = Section
    form_class = SectionForm
    template_name = "academics/section_form.html"
    page_title = "Add Section"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"section.create {self.object}")
        messages.success(self.request, "Section added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:sections")


class SectionUpdateView(EdFlowMixin, UpdateView):
    model = Section
    form_class = SectionForm
    template_name = "academics/section_form.html"
    context_object_name = "section"
    page_title = "Edit Section"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Section updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:sections")


class SubjectListView(EdFlowMixin, SearchMixin, ListView):
    model = Subject
    template_name = "academics/subject_list.html"
    context_object_name = "subjects"
    page_title = "Subjects"
    page_subtitle = "Subjects taught and their codes"
    active_page = "academics"
    search_fields = ["name", "code"]
    search_placeholder = "Search subjects…"


class SubjectCreateView(EdFlowMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = "academics/subject_form.html"
    page_title = "Add Subject"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"subject.create {self.object.name}")
        messages.success(self.request, f"Subject {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:subjects")


class SubjectUpdateView(EdFlowMixin, UpdateView):
    model = Subject
    form_class = SubjectForm
    template_name = "academics/subject_form.html"
    context_object_name = "subject"
    page_title = "Edit Subject"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Subject updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:subjects")


class RoomListView(EdFlowMixin, SearchMixin, ListView):
    model = Room
    template_name = "academics/room_list.html"
    context_object_name = "rooms"
    page_title = "Rooms"
    page_subtitle = "Classrooms and labs used by the timetable solver"
    active_page = "academics"
    search_fields = ["name", "room_type"]
    search_placeholder = "Search rooms…"


class RoomCreateView(EdFlowMixin, CreateView):
    model = Room
    form_class = RoomForm
    template_name = "academics/room_form.html"
    page_title = "Add Room"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"room.create {self.object.name}")
        messages.success(self.request, f"Room {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:rooms")


class RoomUpdateView(EdFlowMixin, UpdateView):
    model = Room
    form_class = RoomForm
    template_name = "academics/room_form.html"
    context_object_name = "room"
    page_title = "Edit Room"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Room updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:rooms")


class HomeworkListView(EdFlowMixin, SearchMixin, ListView):
    model = Homework
    template_name = "academics/homework_list.html"
    context_object_name = "homeworks"
    paginate_by = 20
    page_title = "Homework & Assignments"
    page_subtitle = "Tasks, deadlines, submissions and grading"
    active_page = "academics"
    search_fields = ["title", "subject__name", "klass__name", "teacher__first_name"]
    search_placeholder = "Search homework…"

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "klass", "section", "subject", "teacher"
        )
        staff = getattr(self.request.user, "staff", None)
        if staff:
            qs = qs.filter(teacher=staff)
        klass = self.request.GET.get("klass", "")
        subject = self.request.GET.get("subject", "")
        kind = self.request.GET.get("kind", "")
        if klass.isdigit():
            qs = qs.filter(klass_id=int(klass))
        if subject.isdigit():
            qs = qs.filter(subject_id=int(subject))
        if kind in ("homework", "assignment"):
            qs = qs.filter(kind=kind)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["klasses"] = Class.objects.all()
        ctx["subjects"] = Subject.objects.all()
        ctx["current_klass"] = self.request.GET.get("klass", "")
        ctx["current_subject"] = self.request.GET.get("subject", "")
        ctx["current_kind"] = self.request.GET.get("kind", "")
        ctx["today"] = timezone.localdate()
        return ctx


class HomeworkCreateView(EdFlowMixin, CreateView):
    model = Homework
    form_class = HomeworkForm
    template_name = "academics/homework_form.html"
    page_title = "Add Homework"
    page_subtitle = "Set a task or assignment for a class"
    active_page = "academics"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"homework.create {self.object.pk} {self.object.title}")
        messages.success(self.request, f"Homework “{self.object.title}” created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:homework_detail", args=[self.object.pk])


class HomeworkUpdateView(EdFlowMixin, UpdateView):
    model = Homework
    form_class = HomeworkForm
    template_name = "academics/homework_form.html"
    context_object_name = "homework"
    page_title = "Edit Homework"
    page_subtitle = "Update the task details and deadline"
    active_page = "academics"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Homework updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:homework_detail", args=[self.object.pk])


class HomeworkDeleteView(EdFlowMixin, DeleteView):
    model = Homework
    template_name = "academics/confirm_delete.html"
    context_object_name = "homework"
    success_url = reverse_lazy("academics:homework")
    active_page = "academics"
    extra_context = {"heading": "Delete Homework", "cancel_url": "academics:homework"}

    def form_valid(self, form):
        audit(self.request, f"homework.delete {self.object.pk} {self.object.title}")
        messages.success(self.request, "Homework deleted.")
        return super().form_valid(form)


class HomeworkDetailView(EdFlowMixin, DetailView):
    model = Homework
    template_name = "academics/homework_detail.html"
    context_object_name = "homework"
    active_page = "academics"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.object.title
        ctx["page_subtitle"] = f"{self.object.get_kind_display()} · {self.object.klass}"
        submissions = list(
            self.object.submissions.select_related("student").order_by("-submitted_on")
        )
        ctx["submissions"] = submissions
        ctx["grade_rows"] = [
            (submission, SubmissionGradeForm(instance=submission))
            for submission in submissions
        ]
        students = Student.objects.filter(klass=self.object.klass, status="active")
        if self.object.section_id:
            students = students.filter(section=self.object.section)
        user_student = getattr(self.request.user, "student", None)
        ctx["submission_form"] = SubmissionForm(
            students=students, hide_student=bool(user_student)
        )
        ctx["my_student"] = user_student
        ctx["today"] = timezone.localdate()
        return ctx


class SyllabusListView(EdFlowMixin, SearchMixin, ListView):
    model = Syllabus
    template_name = "academics/syllabus_list.html"
    context_object_name = "syllabi"
    paginate_by = 20
    page_title = "Syllabus"
    page_subtitle = "Curriculum plans per class, subject and term"
    active_page = "academics"
    search_fields = ["title", "klass__name", "subject__name", "term__name"]
    search_placeholder = "Search syllabus…"

    def get_queryset(self):
        return super().get_queryset().select_related("klass", "subject", "term")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["klasses"] = Class.objects.all()
        return ctx


class SyllabusCreateView(EdFlowMixin, CreateView):
    model = Syllabus
    form_class = SyllabusForm
    template_name = "academics/syllabus_form.html"
    page_title = "Add Syllabus"
    page_subtitle = "Define a syllabus unit for a class and subject"
    active_page = "academics"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        resp = super().form_valid(form)
        audit(self.request, f"syllabus.create {self.object.pk} {self.object.title}")
        messages.success(self.request, "Syllabus unit added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:syllabus")


class SyllabusUpdateView(EdFlowMixin, UpdateView):
    model = Syllabus
    form_class = SyllabusForm
    template_name = "academics/syllabus_form.html"
    context_object_name = "syllabus"
    page_title = "Edit Syllabus"
    page_subtitle = "Update the syllabus unit"
    active_page = "academics"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Syllabus unit updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("academics:syllabus")


class SyllabusDeleteView(EdFlowMixin, DeleteView):
    model = Syllabus
    template_name = "academics/confirm_delete.html"
    context_object_name = "syllabus"
    success_url = reverse_lazy("academics:syllabus")
    active_page = "academics"
    extra_context = {"heading": "Delete Syllabus", "cancel_url": "academics:syllabus"}

    def form_valid(self, form):
        audit(self.request, f"syllabus.delete {self.object.pk} {self.object.title}")
        messages.success(self.request, "Syllabus unit deleted.")
        return super().form_valid(form)


@login_required
def submission_submit(request, pk):
    """Record a student's submission (student submits or staff adds on behalf)."""
    homework = get_object_or_404(
        Homework.objects.select_related("klass", "section"), pk=pk
    )
    if request.method != "POST":
        return redirect("academics:homework_detail", pk=homework.pk)
    students = Student.objects.filter(klass=homework.klass, status="active")
    if homework.section_id:
        students = students.filter(section=homework.section)
    user_student = getattr(request.user, "student", None)
    form = SubmissionForm(
        request.POST, request.FILES, students=students, hide_student=bool(user_student)
    )
    if user_student:
        student = user_student
    elif request.POST.get("student", "").isdigit():
        student = get_object_or_404(Student, pk=int(request.POST["student"]))
    else:
        student = None
    if student is None:
        messages.error(request, "No student is linked to this account.")
        return redirect("academics:homework_detail", pk=homework.pk)
    if not students.filter(pk=student.pk).exists():
        messages.error(request, "This student is not in the assigned class.")
        return redirect("academics:homework_detail", pk=homework.pk)
    if not form.is_valid():
        messages.error(request, "Please provide text or an attachment to submit.")
        return redirect("academics:homework_detail", pk=homework.pk)
    submission = form.save(commit=False)
    submission.homework = homework
    submission.student = student
    submission.submitted_on = timezone.now()
    submission.status = (
        SubmissionStatus.LATE
        if timezone.localdate() > homework.due_date
        else SubmissionStatus.SUBMITTED
    )
    try:
        submission.save()
    except IntegrityError:
        messages.error(request, "This student has already submitted.")
        return redirect("academics:homework_detail", pk=homework.pk)
    audit(request, f"submission.submit {submission.pk} homework={homework.pk}")
    messages.success(request, f"Submission recorded for {student.full_name}.")
    return redirect("academics:homework_detail", pk=homework.pk)


@login_required
def submission_grade(request, pk):
    """Grade a submission: marks + teacher remark (POST only)."""
    submission = get_object_or_404(
        Submission.objects.select_related("homework", "student"), pk=pk
    )
    if request.method != "POST":
        return redirect("academics:homework_detail", pk=submission.homework_id)
    form = SubmissionGradeForm(request.POST, instance=submission)
    if form.is_valid():
        submission = form.save(commit=False)
        submission.status = SubmissionStatus.GRADED
        submission.graded_by = request.user
        submission.save()
        audit(
            request,
            f"submission.grade {submission.pk} marks={submission.marks}",
        )
        messages.success(
            request, f"Graded {submission.student.full_name}'s submission."
        )
    else:
        messages.error(request, "Could not save the grade.")
    return redirect("academics:homework_detail", pk=submission.homework_id)