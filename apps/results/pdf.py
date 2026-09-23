"""ReportLab PDF generation for report cards and result sheets (spec §14).

Follows the codebase's existing ReportLab pattern (see payroll, reports exports).
"""

import io
from itertools import chain

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.exams.models import ExamSubject, Mark
from apps.results.models import Result
from apps.school.models import SchoolProfile

GREEN = colors.HexColor("#047857")
LIGHT_GREEN = colors.HexColor("#ecfdf5")
GREY = colors.HexColor("#6b7280")


def _school_header(name="EdFlow School", address="", phone=""):
    phone_line = f" · {phone}" if phone else ""
    return f"<b>{name}</b> · {address}{phone_line}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "school": ParagraphStyle(
            "school", parent=base["Title"], fontSize=16, spaceAfter=2,
            textColor=GREEN,
        ),
        "sub": ParagraphStyle(
            "sub", parent=base["Normal"], fontSize=9, textColor=GREY,
        ),
        "heading": ParagraphStyle(
            "heading", parent=base["Heading2"], fontSize=12, spaceBefore=4,
            spaceAfter=2, textColor=GREEN,
        ),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=8),
        "cellc": ParagraphStyle(
            "cellc", parent=base["Normal"], fontSize=8, alignment=TA_CENTER,
        ),
        "cellr": ParagraphStyle(
            "cellr", parent=base["Normal"], fontSize=8, alignment=TA_RIGHT,
        ),
        "th": ParagraphStyle(
            "th", parent=base["Normal"], fontSize=8, textColor=colors.white,
        ),
        "thc": ParagraphStyle(
            "thc", parent=base["Normal"], fontSize=8, alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "note": ParagraphStyle(
            "note", parent=base["Normal"], fontSize=9, spaceAfter=4,
        ),
    }


def _table_style(header_rows=1):
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), GREEN),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )


def report_card_pdf(exam, student):
    """A professional single-student report card (ReportLab)."""
    school = SchoolProfile.objects.first()
    st = _styles()
    subjects = ExamSubject.objects.filter(exam=exam, klass=student.klass).select_related(
        "subject"
    )
    marks = {
        m.exam_subject_id: m
        for m in Mark.objects.filter(exam_subject__in=subjects, student=student)
    }
    rows = [(es, marks.get(es.pk)) for es in subjects]
    result = Result.objects.filter(exam=exam, student=student).first()
    total_max = sum((es.max_marks for es in subjects), 0)
    total_obtained = sum((m.effective_marks for es, m in rows if m), 0)
    percentage = round(total_obtained * 100 / total_max, 2) if total_max else 0

    header = [
        Paragraph(_school_header(
            school.name if school else "EdFlow School",
            school.address or "",
            school.phone or "",
        ), st["school"]),
        Paragraph(
            f"<b>REPORT CARD</b><br/>{exam.name} · {exam.get_status_display()}",
            st["sub"],
        ),
    ]

    info_data = [
        [
            Paragraph("Name", st["cell"]), Paragraph(f"<b>{student.full_name}</b>", st["cell"]),
            Paragraph("Admission No", st["cell"]), Paragraph(f"<b>{student.admission_number}</b>", st["cell"]),
        ],
        [
            Paragraph("Class / Section", st["cell"]),
            Paragraph(f"<b>{student.klass or '—'}{' / ' + student.section.name if student.section else ''}</b>", st["cell"]),
            Paragraph("Status", st["cell"]), Paragraph(f"<b>{student.get_status_display()}</b>", st["cell"]),
        ],
    ]
    info = Table(info_data, colWidths=[30 * mm, 55 * mm, 32 * mm, 45 * mm])
    info.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdf4")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f0fdf4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    table_data = [[
        Paragraph("Subject", st["th"]),
        Paragraph("Max", st["thc"]),
        Paragraph("Obtained", st["thc"]),
        Paragraph("Grade", st["thc"]),
        Paragraph("Pass", st["thc"]),
        Paragraph("Teacher Remark", st["th"]),
    ]]
    for es, m in rows:
        if m:
            obtained = "A" if m.is_absent else (str(m.marks_obtained) if m.marks_obtained is not None else "—")
            grade = m.grade or "—"
            passed = "Pass" if m.is_pass else "Fail"
            remark = m.teacher_remark or ""
        else:
            obtained = grade = passed = "—"
            remark = ""
        table_data.append([
            Paragraph(es.subject.name, st["cell"]),
            Paragraph(str(es.max_marks), st["cellc"]),
            Paragraph(obtained, st["cellc"]),
            Paragraph(grade, st["cellc"]),
            Paragraph(passed, st["cellc"]),
            Paragraph(remark, st["cell"]),
        ])
    table_data.append([
        Paragraph("<b>Total</b>", st["cell"]),
        Paragraph(str(total_max), st["cellc"]),
        Paragraph(str(total_obtained), st["cellc"]),
        Paragraph(f"<b>{result.grade if result else '—'}</b>", st["cellc"]),
        Paragraph(f"{'<b>Pass</b>' if result and result.is_pass else '<b>Fail</b>' if result else '—'}", st["cellc"]),
        Paragraph("", st["cell"]),
    ])
    body = Table(table_data, colWidths=[55 * mm, 18 * mm, 20 * mm, 18 * mm, 18 * mm, 53 * mm])
    body.setStyle(_table_style())

    summary_data = [
        [
            Paragraph("Percentage", st["cell"]),
            Paragraph(f"<b>{percentage}%</b>", st["cellc"]),
            Paragraph("Grade", st["cell"]),
            Paragraph(f"<b>{result.grade or '—'}</b>", st["cellc"]),
            Paragraph("Class Position", st["cell"]),
            Paragraph(f"<b>{result.class_position or '—'}</b>", st["cellc"]),
        ],
        [
            Paragraph("GPA", st["cell"]),
            Paragraph(f"<b>{result.gpa or '—'}</b>", st["cellc"]),
            Paragraph("Cumulative %", st["cell"]),
            Paragraph(f"<b>{result.weighted_percentage or '—'}</b>", st["cellc"]),
            Paragraph("Exam Type", st["cell"]),
            Paragraph(f"<b>{exam.exam_type}</b>", st["cellc"]),
        ],
    ]
    summary = Table(summary_data, colWidths=[38 * mm, 28 * mm, 32 * mm, 30 * mm, 32 * mm, 22 * mm])
    summary.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREEN),
                ("BACKGROUND", (2, 0), (2, -1), LIGHT_GREEN),
                ("BACKGROUND", (4, 0), (4, -1), LIGHT_GREEN),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    story = [
        Table([[header[0]], [header[1]]], colWidths=[180 * mm]),
        Spacer(1, 6),
        info,
        Spacer(1, 6),
        body,
        Spacer(1, 6),
        summary,
        Spacer(1, 8),
    ]
    if result and result.remarks:
        story.append(Paragraph(f"Remarks: {result.remarks}", st["note"]))

    signs_data = [[
        Paragraph("________________&nbsp;&nbsp;Parent / Guardian", st["cell"]),
        Paragraph("________________&nbsp;&nbsp;Class Teacher", st["cell"]),
        Paragraph("________________&nbsp;&nbsp;Principal", st["cell"]),
    ]]
    signs = Table(signs_data, colWidths=[60 * mm, 60 * mm, 60 * mm])
    signs.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")])
    )
    story.append(Spacer(1, 18))
    story.append(signs)
    story.append(
        Spacer(1, 8)
    )
    story.append(
        Paragraph(
            f"Generated on {__import__('datetime').date.today():%d %b %Y} · EdFlow Exams",
            st["sub"],
        )
    )

    return _build(story, f"report-card-{student.admission_number}.pdf", pagesize=A4)


def result_sheet_pdf(exam, results):
    """A class-wide result sheet: one row per student (ReportLab)."""
    school = SchoolProfile.objects.first()
    st = _styles()

    data = [[
        Paragraph("#", st["thc"]),
        Paragraph("Admission No", st["th"]),
        Paragraph("Student", st["th"]),
        Paragraph("Class", st["th"]),
        Paragraph("Total", st["thc"]),
        Paragraph("%", st["thc"]),
        Paragraph("Cum %", st["thc"]),
        Paragraph("Grade", st["thc"]),
        Paragraph("GPA", st["thc"]),
        Paragraph("Pos", st["thc"]),
        Paragraph("Result", st["thc"]),
    ]]
    for i, r in enumerate(results, start=1):
        data.append([
            Paragraph(str(i), st["cellc"]),
            Paragraph(r.student.admission_number, st["cell"]),
            Paragraph(f"<b>{r.student.full_name}</b>", st["cell"]),
            Paragraph(str(r.student.klass or "—"), st["cell"]),
            Paragraph(f"{r.total_obtained}/{r.total_max}", st["cellc"]),
            Paragraph(f"{r.percentage}%", st["cellc"]),
            Paragraph(f"{r.weighted_percentage}%", st["cellc"]),
            Paragraph(r.grade or "—", st["cellc"]),
            Paragraph(str(r.gpa or "—"), st["cellc"]),
            Paragraph(str(r.class_position or "—"), st["cellc"]),
            Paragraph("<font color='green'><b>Pass</b></font>" if r.is_pass else "<font color='red'><b>Fail</b></font>", st["cellc"]),
        ])
    body = Table(data, colWidths=[10 * mm, 26 * mm, 45 * mm, 24 * mm, 24 * mm, 16 * mm, 18 * mm, 14 * mm, 14 * mm, 12 * mm, 16 * mm])
    body.setStyle(_table_style())

    header = [
        Paragraph(_school_header(
            school.name if school else "EdFlow School",
            school.address or "",
            school.phone or "",
        ), st["school"]),
        Paragraph(
            f"<b>RESULT SHEET — {exam.name.upper()}</b> ({exam.get_status_display()}) · {len(results)} student(s)",
            st["sub"],
        ),
    ]

    story = [
        Table([[header[0]], [header[1]]], colWidths=[260 * mm]),
        Spacer(1, 6),
        body,
        Spacer(1, 8),
        Paragraph(
            f"Generated on {__import__('datetime').date.today():%d %b %Y} · EdFlow Exams",
            st["sub"],
        ),
    ]
    return _build(
        story, f"result-sheet-{exam.pk}.pdf", pagesize=landscape(A4)
    )


def _build(story, filename, pagesize=A4):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response