import io
import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.exams.models import Exam, Mark
from apps.results.models import Result
from apps.students.models import Student

from .forms import ProgressRecordForm
from .models import ProgressRecord


class ProgressListView(EdFlowMixin, SearchMixin, ListView):
    model = Student
    template_name = "progress/progress_list.html"
    context_object_name = "students"
    paginate_by = 25
    page_title = "Student Progress"
    page_subtitle = "Development tracking, exam trends and teacher remarks"
    active_page = "progress"
    search_fields = [
        "admission_number",
        "first_name",
        "middle_name",
        "last_name",
    ]
    search_placeholder = "Search by admission number or name…"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("klass", "section")
            .order_by("admission_number")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ids = [s.pk for s in self.object_list]
        rows = (
            Result.objects.filter(student_id__in=ids)
            .order_by("exam__start_date", "exam__created_at", "id")
            .values_list("student_id", "percentage")
        )
        latest = {}
        trend = {}
        for student_id, percentage in rows:
            pct = float(percentage)
            latest[student_id] = pct
            trend.setdefault(student_id, []).append(pct)
        ctx["latest_pct"] = latest
        ctx["trend"] = {k: json.dumps(v) for k, v in trend.items()}
        records = ProgressRecord.objects.filter(student_id__in=ids).values(
            "student_id"
        ).order_by("student_id")
        counts = {}
        for item in records:
            counts[item["student_id"]] = counts.get(item["student_id"], 0) + 1
        ctx["record_counts"] = counts
        return ctx


class ProgressDetailView(EdFlowMixin, DetailView):
    model = Student
    template_name = "progress/progress_detail.html"
    context_object_name = "student"
    pk_url_kwarg = "student_pk"
    active_page = "progress"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        student = self.object
        ctx["page_title"] = f"Progress — {student.full_name}"
        ctx["page_subtitle"] = f"{student.admission_number} · performance across terms and years"

        exams = list(
            Exam.objects.filter(results__student=student)
            .order_by("start_date", "created_at", "id")
            .distinct()
        )
        labels = []
        overall = []
        subject_data = {}
        results_by_exam = {
            r.exam_id: r
            for r in Result.objects.filter(exam__in=exams, student=student)
        }
        for idx, exam in enumerate(exams):
            type_name = exam.exam_type.name if exam.exam_type_id else ""
            labels.append(f"{type_name} · {exam.name}" if type_name else exam.name)
            result = results_by_exam.get(exam.pk)
            overall.append(float(result.percentage) if result else None)
            marks = Mark.objects.filter(
                exam_subject__exam=exam, student=student
            ).select_related("exam_subject__subject")
            for mark in marks:
                name = mark.exam_subject.subject.name
                if name not in subject_data:
                    subject_data[name] = [None] * len(exams)
                subject_data[name][idx] = float(mark.percentage)

        ctx["exam_labels"] = json.dumps(labels)
        ctx["overall_values"] = json.dumps(overall)
        ctx["subject_names"] = json.dumps(list(subject_data.keys()))
        ctx["subject_series"] = json.dumps(list(subject_data.values()))

        remarks = list(
            Mark.objects.filter(student=student)
            .exclude(teacher_remark="")
            .order_by("-exam_subject__exam__start_date", "-exam_subject__exam__created_at")
            .values_list("teacher_remark", "exam_subject__exam__name")[:10]
        )
        ctx["remarks"] = [{"text": text, "exam": exam_name} for text, exam_name in remarks]

        ctx["records"] = ProgressRecord.objects.filter(student=student).select_related(
            "subject", "term", "year"
        )[:20]
        ctx["record_count"] = ProgressRecord.objects.filter(student=student).count()

        ctx["attendance_available"] = self._attendance_correlation(ctx)
        return ctx

    def _attendance_correlation(self, ctx):
        try:
            from apps.attendance.models import StudentAttendance
        except Exception:
            return False
        qs = StudentAttendance.objects.filter(student=self.object)
        total_days = qs.values("date").distinct().count()
        if not total_days:
            ctx["attendance"] = {"avg": None, "days": 0, "today_present": False}
            return True
        present_days = qs.filter(status__in=["present", "late", "excused"]).values(
            "date"
        ).distinct().count()
        ctx["attendance"] = {
            "avg": round(present_days * 100 / total_days, 1),
            "days": total_days,
            "today_present": qs.filter(
                date=timezone.localdate(), status="present"
            ).exists(),
        }
        return True


class ProgressRecordCreateView(EdFlowMixin, CreateView):
    model = ProgressRecord
    form_class = ProgressRecordForm
    template_name = "progress/progress_record_form.html"
    page_title = "Add Progress Record"
    page_subtitle = "Assessment, homework, behaviour or skill score (0–100)"
    active_page = "progress"

    def get_initial(self):
        return {"student_id": self.request.GET.get("student")}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"progress.create {self.object.pk} student={self.object.student_id} score={self.object.score}",
            object_type="ProgressRecord",
            object_id=self.object.pk,
        )
        messages.success(
            self.request, f"Progress record saved for {self.object.student.full_name}."
        )
        return resp

    def get_success_url(self):
        return reverse_lazy(
            "progress:records", kwargs={"student_pk": self.object.student_id}
        )


class ProgressRecordsView(EdFlowMixin, ListView):
    model = ProgressRecord
    template_name = "progress/progress_records.html"
    context_object_name = "records"
    paginate_by = 25
    active_page = "progress"

    def get_queryset(self):
        self.student = get_object_or_404(Student, pk=self.kwargs["student_pk"])
        return (
            ProgressRecord.objects.filter(student=self.student)
            .select_related("subject", "term", "year", "created_by")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["student"] = self.student
        ctx["page_title"] = f"Progress Records — {self.student.full_name}"
        ctx["page_subtitle"] = f"{self.student.admission_number} · all logged records"
        return ctx


class ProgressRecordUpdateView(EdFlowMixin, UpdateView):
    model = ProgressRecord
    form_class = ProgressRecordForm
    template_name = "progress/progress_record_form.html"
    page_title = "Edit Progress Record"
    active_page = "progress"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"progress.update {self.object.pk} student={self.object.student_id} score={self.object.score}",
            object_type="ProgressRecord",
            object_id=self.object.pk,
        )
        messages.success(self.request, "Progress record updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy(
            "progress:records", kwargs={"student_pk": self.object.student_id}
        )


class ProgressRecordDeleteView(EdFlowMixin, DeleteView):
    model = ProgressRecord
    template_name = "progress/progress_record_confirm_delete.html"
    active_page = "progress"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Progress Record"
        ctx["student"] = self.object.student
        return ctx

    def form_valid(self, form):
        student_id = self.object.student_id
        audit(
            self.request,
            f"progress.delete {self.object.pk}",
            object_type="ProgressRecord",
            object_id=self.object.pk,
        )
        messages.success(self.request, "Progress record deleted.")
        self.extra_success_url = reverse_lazy(
            "progress:records", kwargs={"student_pk": student_id}
        )
        return super().form_valid(form)

    def get_success_url(self):
        return getattr(self, "extra_success_url", reverse_lazy("progress:list"))


class ProgressReportPdfView(EdFlowMixin, View):
    """Printable/PDF progress report: exam trend, subject marks and records."""

    def get(self, request, student_pk):
        student = get_object_or_404(Student, pk=student_pk)

        from apps.school.models import SchoolProfile

        school = SchoolProfile.objects.first()

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SchoolTitle", parent=styles["Title"], fontSize=15, spaceAfter=2
        )
        addr_style = ParagraphStyle(
            "Addr", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#555555")
        )
        h1 = ParagraphStyle("H1", parent=styles["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
        h2 = ParagraphStyle("H2", parent=styles["Heading3"], fontSize=10, spaceBefore=6, spaceAfter=2)
        cell = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8)

        story = []
        story.append(Paragraph(school.name if school else "EdFlow School", title_style))
        story.append(Paragraph((school.address if school else "") or "", addr_style))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Student Progress Report<br/><b>{student.full_name}</b> — {student.admission_number}", h1))

        exams = list(
            Exam.objects.filter(results__student=student)
            .order_by("start_date", "created_at", "id")
            .distinct()
        )
        results_by_exam = {
            r.exam_id: r
            for r in Result.objects.filter(exam__in=exams, student=student)
        }

        if exams:
            story.append(Paragraph("Examination History (overall %)", h2))
            data = [["Exam", "Type", "Percentage", "Grade", "Position"]]
            for exam in exams:
                result = results_by_exam.get(exam.pk)
                if result:
                    data.append(
                        [
                            exam.name,
                            exam.exam_type.name if exam.exam_type_id else "—",
                            f"{result.percentage}%",
                            result.grade or "—",
                            result.class_position or "—",
                        ]
                    )
            t = Table(data, colWidths=[45 * mm, 35 * mm, 25 * mm, 20 * mm, 20 * mm])
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaed")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(t)

        records = list(
            ProgressRecord.objects.filter(student=student)
            .select_related("subject", "term", "year")[:30]
        )
        if records:
            story.append(Paragraph("Progress Records", h2))
            data = [["Date", "Category", "Subject", "Score", "Remark"]]
            for r in records:
                data.append(
                    [
                        timezone.localtime(r.created_at).strftime("%d %b %Y"),
                        r.get_category_display(),
                        r.subject.name if r.subject_id else "—",
                        f"{r.score}%",
                        r.remark,
                    ]
                )
            t = Table(data, colWidths=[22 * mm, 28 * mm, 28 * mm, 15 * mm, 52 * mm])
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaed")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(t)

        story.append(Spacer(1, 8))
        story.append(
            Paragraph(
                f"Generated on {timezone.localdate():%d %b %Y} · EdFlow Progress",
                addr_style,
            )
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )
        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(buffer.read(), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="progress-{student.admission_number}.pdf"'
        )
        return response