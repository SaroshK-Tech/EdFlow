from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin
from apps.exams.models import Exam, ExamSubject, GradeBoundary, Mark
from apps.students.models import Student

from .models import Result

from . import pdf as pdf_export


def _subject_positions(exam, klass):
    """Rank students per subject within a class: {exam_subject_id: {student_id: rank}}."""
    positions = {}
    subjects = ExamSubject.objects.filter(exam=exam, klass=klass)
    students = list(Student.objects.filter(klass=klass, status="active").values_list("id", flat=True))
    for es in subjects:
        marks = list(
            Mark.objects.filter(exam_subject=es, student_id__in=students).order_by(
                "-is_absent", "-marks_obtained", "student__first_name"
            )
        )
        ranks = {}
        rank = 0
        last = object()
        for m in marks:
            if m.is_absent or m.marks_obtained != last:
                rank += 1
                last = m.marks_obtained
            ranks[m.student_id] = rank
        positions[es.pk] = ranks
    return positions


def _exam_percentage(exam, klass_id, student):
    """A student's percentage in one exam's class, or None if they sat none."""
    subjects = exam.subjects.filter(klass_id=klass_id)
    total_max = sum((s.max_marks for s in subjects), 0)
    if not total_max:
        return None
    obtained = Decimal("0")
    sat = False
    for es in subjects:
        mark = Mark.objects.filter(exam_subject=es, student=student).first()
        if mark is None:
            continue
        sat = True
        obtained += mark.effective_marks
    if not sat:
        return None
    return round(obtained * 100 / total_max, 2)


def _weighted_percentage(exam, student):
    """Cumulative % over the class's exams, weighted by exam-type weightage."""
    candidate = Exam.objects.filter(subjects__klass_id=student.klass_id).distinct()
    if exam.academic_year_id:
        candidate = candidate.filter(academic_year_id=exam.academic_year_id)
    weighted = Decimal("0")
    weight_sum = Decimal("0")
    for other in candidate.select_related("exam_type"):
        pct = _exam_percentage(other, student.klass_id, student)
        if pct is None:
            continue
        weight = other.exam_type.weightage
        weighted += pct * weight
        weight_sum += weight
    if not weight_sum:
        return Decimal("0")
    return (weighted / weight_sum).quantize(Decimal("0.01"))


def generate_results(exam):
    """(Re)compute Result rows for every active student in the exam's classes."""
    with transaction.atomic():
        Result.objects.filter(exam=exam).delete()
        klass_ids = list(exam.subjects.values_list("klass_id", flat=True).distinct())
        students = Student.objects.filter(klass_id__in=klass_ids, status="active")

        rows = []
        for student in students:
            subjects = exam.subjects.filter(klass_id=student.klass_id)
            total_max = sum((s.max_marks for s in subjects), 0)
            if not total_max:
                continue
            total_obtained = 0
            all_pass = True
            graded = 0
            for es in subjects:
                mark = Mark.objects.filter(exam_subject=es, student=student).first()
                if mark is None:
                    all_pass = False
                    continue
                graded += 1
                total_obtained += mark.effective_marks
                if not mark.is_pass:
                    all_pass = False
            percentage = round(total_obtained * 100 / total_max, 2)
            boundary = GradeBoundary.for_percentage(percentage)
            rows.append(
                Result(
                    exam=exam,
                    student=student,
                    total_max=total_max,
                    total_obtained=total_obtained,
                    percentage=percentage,
                    weighted_percentage=_weighted_percentage(exam, student),
                    grade=boundary.name if boundary else "",
                    gpa=boundary.gpa if boundary else None,
                    is_pass=all_pass and graded > 0,
                )
            )
        Result.objects.bulk_create(rows)

        for klass_id in klass_ids:
            ranked = Result.objects.filter(
                exam=exam, student__klass_id=klass_id
            ).order_by("-percentage", "-total_obtained", "student__first_name")
            for position, result in enumerate(ranked, start=1):
                if result.class_position != position:
                    result.class_position = position
                    result.save(update_fields=["class_position"])
    return len(rows)


class ExamResultListView(EdFlowMixin, ListView):
    """Overview of examinations with computed results (spec §14)."""

    template_name = "results/exam_list.html"
    context_object_name = "exams"
    paginate_by = 25
    page_title = "Results"
    page_subtitle = "Examinations and their computed results"
    active_page = "results"

    def get_queryset(self):
        from django.db.models import Count

        return (
            Exam.objects.all()
            .select_related("exam_type", "academic_year")
            .annotate(result_count=Count("results", distinct=True))
            .order_by("-start_date", "-created_at")
        )


class ResultListView(EdFlowMixin, ListView):
    """Per-exam results overview (also the generate/publish hub)."""

    template_name = "results/result_list.html"
    context_object_name = "results"
    active_page = "results"
    paginate_by = 50

    def get_queryset(self):
        self.exam = get_object_or_404(Exam, pk=self.kwargs["pk"])
        return (
            Result.objects.filter(exam=self.exam)
            .select_related("student", "student__klass", "student__section")
            .order_by("student__klass__name", "class_position")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["exam"] = self.exam
        ctx["page_title"] = f"Results — {self.exam.name}"
        ctx["page_subtitle"] = str(self.exam.exam_type)
        ctx["klasses"] = (
            ExamSubject.objects.filter(exam=self.exam)
            .values_list("klass__id", "klass__name")
            .distinct()
        )
        return ctx


def result_generate(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if request.method != "POST":
        return redirect("results:detail", pk=exam.pk)
    count = generate_results(exam)
    audit(request, f"results.generate exam={exam.pk} count={count}")
    messages.success(request, f"Generated {count} result(s) for {exam.name}.")
    return redirect("results:detail", pk=exam.pk)


class ResultSheetView(EdFlowMixin, View):
    """Printable summary sheet: one row per student."""

    active_page = "exams"

    def get(self, request, pk):
        exam = get_object_or_404(Exam, pk=pk)
        results = (
            Result.objects.filter(exam=exam)
            .select_related("student", "student__klass", "student__section")
            .order_by("student__klass__name", "class_position")
        )
        klass_id = request.GET.get("class")
        if klass_id:
            results = results.filter(student__klass_id=klass_id)
        return render(
            request,
            "results/result_sheet.html",
            {
                "exam": exam,
                "results": results,
                "page_title": f"Result Sheet — {exam.name}",
                "active_page": "exams",
            },
        )


class TabulationView(EdFlowMixin, View):
    """Printable subject-by-subject grid for one class."""

    active_page = "exams"

    def get(self, request, pk, class_pk):
        from apps.academics.models import Class

        exam = get_object_or_404(Exam, pk=pk)
        klass = get_object_or_404(Class, pk=class_pk)
        subjects = list(
            ExamSubject.objects.filter(exam=exam, klass=klass)
            .select_related("subject")
            .order_by("subject__name")
        )
        students = list(
            Student.objects.filter(klass=klass, status="active").order_by(
                "roll_number", "first_name"
            )
        )
        marks = {}
        for m in Mark.objects.filter(
            exam_subject__in=subjects, student__in=students
        ).select_related("exam_subject"):
            marks[(m.exam_subject_id, m.student_id)] = m
        results = {
            r.student_id: r
            for r in Result.objects.filter(exam=exam, student__in=students)
        }
        positions = _subject_positions(exam, klass)
        rows = []
        for student in students:
            cells = []
            for es in subjects:
                m = marks.get((es.pk, student.pk))
                cells.append(
                    {
                        "mark": m,
                        "rank": (positions.get(es.pk, {}) or {}).get(student.pk),
                    }
                )
            rows.append({"student": student, "cells": cells, "result": results.get(student.pk)})
        return render(
            request,
            "results/tabulation.html",
            {
                "exam": exam,
                "klass": klass,
                "subjects": subjects,
                "rows": rows,
                "page_title": f"Tabulation — {klass}",
                "active_page": "exams",
            },
        )


class ReportCardPdfView(EdFlowMixin, View):
    """ReportLab PDF report card for one student (spec §14 'Report cards')."""

    active_page = "exams"

    def get(self, request, pk, student_pk):
        exam = get_object_or_404(Exam, pk=pk)
        student = get_object_or_404(Student, pk=student_pk)
        audit(request, f"results.report_card_pdf exam={exam.pk} student={student.pk}")
        return pdf_export.report_card_pdf(exam, student)


class ResultSheetPdfView(EdFlowMixin, View):
    """ReportLab PDF result sheet for an exam / class."""

    active_page = "exams"

    def get(self, request, pk):
        exam = get_object_or_404(Exam, pk=pk)
        results = (
            Result.objects.filter(exam=exam)
            .select_related("student", "student__klass", "student__section")
            .order_by("student__klass__name", "class_position")
        )
        klass_id = request.GET.get("class")
        if klass_id:
            results = results.filter(student__klass_id=klass_id)
        audit(request, f"results.result_sheet_pdf exam={exam.pk} rows={len(results)}")
        return pdf_export.result_sheet_pdf(exam, results)


class ReportCardView(EdFlowMixin, View):
    """Printable student report card."""

    active_page = "exams"

    def get(self, request, pk, student_pk):
        exam = get_object_or_404(Exam, pk=pk)
        student = get_object_or_404(Student, pk=student_pk)
        subjects = ExamSubject.objects.filter(exam=exam, klass=student.klass).select_related(
            "subject"
        )
        rows = []
        for es in subjects:
            mark = Mark.objects.filter(exam_subject=es, student=student).first()
            rows.append({"exam_subject": es, "mark": mark})
        result = Result.objects.filter(exam=exam, student=student).first()
        total_max = sum((es.max_marks for es in subjects), 0)
        total_obtained = sum(
            (r["mark"].effective_marks for r in rows if r["mark"]), 0
        )
        percentage = round(total_obtained * 100 / total_max, 2) if total_max else 0
        return render(
            request,
            "results/report_card.html",
            {
                "exam": exam,
                "student": student,
                "rows": rows,
                "result": result,
                "total_max": total_max,
                "total_obtained": total_obtained,
                "percentage": percentage,
                "page_title": f"Report Card — {student.full_name}",
                "active_page": "exams",
            },
        )
