from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.students.models import Student

from .forms import ExamForm, ExamSubjectForm, ExamTypeForm, GradeBoundaryForm
from .models import Exam, ExamSubject, ExamStatus, ExamType, GradeBoundary, Mark


# --------------------------------------------------------------------------
# Exam settings: grade boundaries + exam types
# --------------------------------------------------------------------------
class GradeBoundaryListView(EdFlowMixin, ListView):
    model = GradeBoundary
    template_name = "exams/gradeboundary_list.html"
    context_object_name = "boundaries"
    page_title = "Grade Boundaries"
    page_subtitle = "Map percentages to grades, GPA and remarks"
    active_page = "exams"


class GradeBoundaryCreateView(EdFlowMixin, CreateView):
    model = GradeBoundary
    form_class = GradeBoundaryForm
    template_name = "exams/exam_settings_form.html"
    page_title = "Add Grade Boundary"
    active_page = "exams"
    extra_context = {"cancel_url": "exams:gradeboundaries"}

    def form_valid(self, form):
        audit(self.request, f"gradeboundary.create {form.instance.name}")
        messages.success(self.request, "Grade boundary added.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("exams:gradeboundaries")


class GradeBoundaryUpdateView(EdFlowMixin, UpdateView):
    model = GradeBoundary
    form_class = GradeBoundaryForm
    template_name = "exams/exam_settings_form.html"
    context_object_name = "object"
    page_title = "Edit Grade Boundary"
    active_page = "exams"
    extra_context = {"cancel_url": "exams:gradeboundaries"}

    def form_valid(self, form):
        messages.success(self.request, "Grade boundary updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("exams:gradeboundaries")


class GradeBoundaryDeleteView(EdFlowMixin, DeleteView):
    model = GradeBoundary
    template_name = "exams/confirm_delete.html"
    success_url = reverse_lazy("exams:gradeboundaries")
    active_page = "exams"
    extra_context = {"heading": "Delete Grade Boundary", "cancel_url": "exams:gradeboundaries"}


class ExamTypeListView(EdFlowMixin, ListView):
    model = ExamType
    template_name = "exams/examtype_list.html"
    context_object_name = "exam_types"
    page_title = "Exam Types"
    page_subtitle = "Categories such as Unit Test, Mid Term and Final"
    active_page = "exams"


class ExamTypeCreateView(EdFlowMixin, CreateView):
    model = ExamType
    form_class = ExamTypeForm
    template_name = "exams/exam_settings_form.html"
    page_title = "Add Exam Type"
    active_page = "exams"
    extra_context = {"cancel_url": "exams:examtypes"}

    def form_valid(self, form):
        messages.success(self.request, "Exam type added.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("exams:examtypes")


class ExamTypeUpdateView(EdFlowMixin, UpdateView):
    model = ExamType
    form_class = ExamTypeForm
    template_name = "exams/exam_settings_form.html"
    context_object_name = "object"
    page_title = "Edit Exam Type"
    active_page = "exams"
    extra_context = {"cancel_url": "exams:examtypes"}

    def form_valid(self, form):
        messages.success(self.request, "Exam type updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("exams:examtypes")


class ExamTypeDeleteView(EdFlowMixin, DeleteView):
    model = ExamType
    template_name = "exams/confirm_delete.html"
    success_url = reverse_lazy("exams:examtypes")
    active_page = "exams"
    extra_context = {"heading": "Delete Exam Type", "cancel_url": "exams:examtypes"}


# --------------------------------------------------------------------------
# Exams
# --------------------------------------------------------------------------
class ExamListView(EdFlowMixin, SearchMixin, ListView):
    model = Exam
    template_name = "exams/exam_list.html"
    context_object_name = "exams"
    paginate_by = 20
    page_title = "Examinations"
    page_subtitle = "Exams, marks entry and results"
    active_page = "exams"
    search_fields = ["name", "exam_type__name", "remarks"]
    search_placeholder = "Search exams…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("exam_type", "academic_year")
        status = self.request.GET.get("status", "")
        if status in dict(ExamStatus.choices):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = ExamStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        return ctx


class ExamCreateView(EdFlowMixin, CreateView):
    model = Exam
    form_class = ExamForm
    template_name = "exams/exam_form.html"
    page_title = "Add Exam"
    active_page = "exams"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"exam.create {self.object.name}")
        messages.success(self.request, f"Exam “{self.object.name}” created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("exams:detail", args=[self.object.pk])


class ExamUpdateView(EdFlowMixin, UpdateView):
    model = Exam
    form_class = ExamForm
    template_name = "exams/exam_form.html"
    context_object_name = "exam"
    page_title = "Edit Exam"
    active_page = "exams"

    def form_valid(self, form):
        messages.success(self.request, "Exam updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("exams:detail", args=[self.object.pk])


class ExamDeleteView(EdFlowMixin, DeleteView):
    model = Exam
    template_name = "exams/confirm_delete.html"
    success_url = reverse_lazy("exams:list")
    active_page = "exams"
    extra_context = {"heading": "Delete Exam", "cancel_url": "exams:list"}


class ExamDetailView(EdFlowMixin, DetailView):
    model = Exam
    template_name = "exams/exam_detail.html"
    context_object_name = "exam"
    active_page = "exams"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.results.models import Result

        ctx["page_title"] = self.object.name
        ctx["page_subtitle"] = str(self.object.exam_type)
        subjects = self.object.subjects.select_related("klass", "subject").order_by(
            "klass__name", "subject__name"
        )
        grouped = {}
        for es in subjects:
            grouped.setdefault(es.klass, []).append(es)
        ctx["subject_groups"] = grouped
        ctx["total_students"] = Student.objects.filter(
            klass__in=[k for k in grouped], status="active"
        ).count()
        ctx["result_count"] = Result.objects.filter(exam=self.object).count()
        return ctx


class ExamSubjectCreateView(EdFlowMixin, CreateView):
    model = ExamSubject
    form_class = ExamSubjectForm
    template_name = "exams/exam_subject_form.html"
    page_title = "Add Exam Subjects"
    active_page = "exams"

    def dispatch(self, request, *args, **kwargs):
        self.exam = get_object_or_404(Exam, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["exam"] = self.exam
        ctx["existing"] = self.exam.subjects.select_related("klass", "subject")
        return ctx

    def form_valid(self, form):
        klass = form.cleaned_data["klass"]
        subjects = form.cleaned_data["subjects"]
        created = 0
        for subject in subjects:
            _, made = ExamSubject.objects.get_or_create(
                exam=self.exam,
                klass=klass,
                subject=subject,
                defaults={
                    "max_marks": form.cleaned_data["max_marks"],
                    "pass_marks": form.cleaned_data["pass_marks"],
                    "weightage": form.cleaned_data["weightage"],
                },
            )
            created += int(made)
        audit(self.request, f"exam.subjects_add exam={self.exam.pk} created={created}")
        messages.success(
            self.request,
            f"Added {created} subject(s) to {self.exam.name} for {klass}.",
        )
        return redirect("exams:detail", pk=self.exam.pk)


class ExamSubjectDeleteView(EdFlowMixin, DeleteView):
    template_name = "exams/confirm_delete.html"
    active_page = "exams"

    def get_queryset(self):
        return ExamSubject.objects.select_related("exam", "klass", "subject")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["heading"] = "Remove Exam Subject"
        ctx["cancel_url"] = "exams:detail"
        ctx["cancel_arg"] = self.object.exam_id
        return ctx

    def form_valid(self, form):
        exam_id = self.object.exam_id
        messages.success(self.request, "Subject removed from exam.")
        response = super().form_valid(form)
        return response

    def get_success_url(self):
        return reverse_lazy("exams:detail", args=[self.object.exam_id])


@login_required
def marks_entry(request, pk):
    """Grid entry of marks for every active student in an exam subject."""
    exam_subject = get_object_or_404(
        ExamSubject.objects.select_related("exam", "klass", "subject"), pk=pk
    )
    students = list(
        Student.objects.filter(klass=exam_subject.klass, status="active").order_by(
            "roll_number", "first_name"
        )
    )
    existing = {
        m.student_id: m
        for m in Mark.objects.filter(
            exam_subject=exam_subject, student__in=students
        )
    }

    if request.method == "POST":
        saved = 0
        errors = 0
        for student in students:
            raw = request.POST.get(f"mark_{student.pk}", "").strip()
            absent = request.POST.get(f"absent_{student.pk}") == "on"
            remark = request.POST.get(f"remark_{student.pk}", "").strip()
            value = None
            if raw:
                try:
                    value = Decimal(raw)
                except InvalidOperation:
                    errors += 1
                    continue
            mark = existing.get(student.pk)
            if mark is None:
                mark = Mark(exam_subject=exam_subject, student=student)
            mark.is_absent = absent
            mark.marks_obtained = None if absent else value
            mark.teacher_remark = remark
            mark.save()
            saved += 1
        audit(request, f"marks.entry exam_subject={exam_subject.pk} saved={saved}")
        if errors:
            messages.warning(request, f"Saved {saved} mark(s); {errors} invalid value(s) skipped.")
        else:
            messages.success(request, f"Saved marks for {saved} student(s).")
        return redirect("exams:detail", pk=exam_subject.exam_id)

    return render(
        request,
        "exams/marks_entry.html",
        {
            "exam_subject": exam_subject,
            "students": students,
            "existing": existing,
            "page_title": f"Marks — {exam_subject.subject}",
            "page_subtitle": f"{exam_subject.exam.name} · {exam_subject.klass}",
            "active_page": "exams",
        },
    )


@login_required
def exam_set_status(request, pk, status):
    """Approve or publish an exam (POST only)."""
    exam = get_object_or_404(Exam, pk=pk)
    if request.method != "POST":
        return redirect("exams:detail", pk=exam.pk)
    if status not in dict(ExamStatus.choices):
        messages.error(request, "Unknown status.")
        return redirect("exams:detail", pk=exam.pk)
    exam.status = status
    exam.save(update_fields=["status"])
    audit(request, f"exam.status {exam.pk} -> {status}")
    messages.success(request, f"{exam.name} marked as {exam.get_status_display()}.")
    return redirect("exams:detail", pk=exam.pk)
