"""ReportLab-based PDF generation for documents & certificates (spec §23).

Everything renders locally, offline-first. School name/address come from
SchoolProfile when configured.
"""

import datetime
import io

from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def school_brand():
    from apps.school.models import SchoolProfile

    profile = SchoolProfile.objects.first()
    if profile is None:
        return {"name": "EdFlow School", "address": ""}
    return {
        "name": getattr(profile, "name", "") or "EdFlow School",
        "address": getattr(profile, "address", "") or "",
    }


def _safe(value):
    value = "" if value is None else str(value)
    return "".join(ch for ch in value if ord(ch) >= 32)


def _render(pdf_name, draw, pagesize=A4):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=pagesize)
    draw(c)
    c.showPage()
    c.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{_safe(pdf_name)}"'
    return response


def _brand_box(c, x, y, w, h):
    c.setStrokeColor(colors.HexColor("#1f4e78"))
    c.setLineWidth(2)
    c.rect(x, y, w, h)
    c.setFillColor(colors.HexColor("#1f4e78"))
    c.rect(x, y, w, 4)


def student_id_pdf(student):
    brand = school_brand()
    w, h = 85 * mm, 55 * mm
    x0, y0 = 6 * mm, 6 * mm

    def draw(c):
        _brand_box(c, x0, y0, w, h)
        inner = x0 + 5 * mm
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x0 + w / 2, y0 + h - 10 * mm, _safe(brand["name"]))
        c.setFont("Helvetica-Bold", 7)
        c.drawString(inner, y0 + h - 21 * mm, "STUDENT IDENTITY CARD")
        c.setFont("Helvetica", 9)
        lines = [
            ("Name", student.full_name or "—"),
            ("Admission No.", student.admission_number or "—"),
            ("Class", student.klass.name if student.klass else "—"),
            ("Roll No.", student.roll_number or "—"),
            ("Blood Group", student.blood_group or "—"),
        ]
        ty = y0 + h - 27 * mm
        for label, value in lines:
            c.setFont("Helvetica-Bold", 8)
            c.drawString(inner, ty, label)
            c.setFont("Helvetica", 9)
            c.drawString(inner + 32 * mm, ty, _safe(value))
            ty -= 5 * mm
        c.setFont("Helvetica", 7)
        c.drawString(inner, y0 + 12 * mm, _safe(brand["address"]))
        c.setFont("Helvetica", 7)
        c.drawRightString(x0 + w - 5 * mm, y0 + 8 * mm, "Valid while enrolled · EdFlow")

    return _render(f"student-id-{student.admission_number}.pdf", draw, pagesize=(w, h))


def staff_id_pdf(staff):
    brand = school_brand()
    w, h = 85 * mm, 55 * mm
    x0, y0 = 6 * mm, 6 * mm

    def draw(c):
        _brand_box(c, x0, y0, w, h)
        inner = x0 + 5 * mm
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x0 + w / 2, y0 + h - 10 * mm, _safe(brand["name"]))
        c.setFont("Helvetica-Bold", 7)
        c.drawString(inner, y0 + h - 21 * mm, "STAFF IDENTITY CARD")
        c.setFont("Helvetica", 9)
        lines = [
            ("Name", staff.full_name or "—"),
            ("Staff No.", staff.employee_code or "—"),
            ("Designation", staff.designation or "—"),
            ("Department", staff.department.name if staff.department else "—"),
            ("Phone", staff.phone or "—"),
        ]
        ty = y0 + h - 27 * mm
        for label, value in lines:
            c.setFont("Helvetica-Bold", 8)
            c.drawString(inner, ty, label)
            c.setFont("Helvetica", 9)
            c.drawString(inner + 30 * mm, ty, _safe(value))
            ty -= 5.2 * mm
        c.setFont("Helvetica", 7)
        c.drawString(inner, y0 + 12 * mm, _safe(brand["address"]))
        c.setFont("Helvetica", 7)
        c.drawRightString(x0 + w - 5 * mm, y0 + 8 * mm, "Issued by EdFlow")

    return _render(f"staff-id-{staff.employee_code}.pdf", draw, pagesize=(w, h))


def _letter_pdf(title, heading, paragraphs, author="", school_name=None):
    """Generic A4 letter: school header + title + body + signature line."""
    brand = school_brand()

    def draw(c):
        c.saveState()
        c.rect(10 * mm, 10 * mm, A4[0] - 20 * mm, A4[1] - 20 * mm)
        c.rect(10 * mm, A4[1] - 24 * mm, A4[0] - 20 * mm, 4 * mm, stroke=0, fill=1)
        c.restoreState()
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(A4[0] / 2, A4[1] - 18 * mm, _safe(school_name or brand["name"]))
        c.setFont("Helvetica", 8)
        c.drawCentredString(A4[0] / 2, A4[1] - 22 * mm, _safe(brand["address"]))
        c.setFont("Times-Bold", 13)
        c.drawString(18 * mm, A4[1] - 40 * mm, _safe(title))
        c.setStrokeColor(colors.grey)
        c.line(18 * mm, A4[1] - 44 * mm, A4[0] - 18 * mm, A4[1] - 44 * mm)
        ty = A4[1] - 62 * mm
        c.setFont("Times-Roman", 11)
        for para in paragraphs:
            words = _wrap(_safe(para), A4[0] - 36 * mm, 11)
            for line in words:
                c.drawString(18 * mm, ty, line)
                ty -= 5.2 * mm
            ty -= 4 * mm
        if author:
            c.drawString(18 * mm, 24 * mm, _safe(author))

    return _render(f"{_safe(title).lower().replace(' ', '-')}.pdf", draw)


def _wrap(text, width, font_size):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if stringWidth(candidate, "Times-Roman", font_size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def certificate_pdf(student, template, extra_paragraphs=()):
    school_name = school_brand()["name"]
    body = template.body or ""
    context = {
        "student_name": student.full_name or "",
        "admission_number": student.admission_number or "",
        "class_name": student.klass.name if student.klass else "",
        "school_name": school_name,
        "date": datetime.date.today().strftime("%d %b %Y"),
    }
    from apps.communication.services import render_body

    paragraphs = [render_body(body, **context)]
    paragraphs.extend(extra_paragraphs)
    return _letter_pdf(
        template.name,
        template.name,
        paragraphs,
        author=f"Administrator · {school_name}",
        school_name=school_name,
    )


def admission_pdf(student, template):
    school_name = school_brand()["name"]
    body = template.body or ""
    context = {
        "student_name": student.full_name or "",
        "admission_number": student.admission_number or "",
        "class_name": student.klass.name if student.klass else "",
        "school_name": school_name,
        "date": datetime.date.today().strftime("%d %b %Y"),
        "joined_date": (student.joined_at or datetime.date.today()).strftime("%d %b %Y"),
    }
    from apps.communication.services import render_body

    return _letter_pdf(
        "Admission Letter",
        "ADMISSION LETTER",
        [render_body(body, **context)] if body else [f"Admission of {student.full_name} confirmed."],
        author=f"Administrator · {school_name}",
        school_name=school_name,
    )


def fee_receipt_pdf(payment):
    school_name = school_brand()["name"]
    lines = [
        f"Receipt: {payment.receipt_number}",
        f"Student: {payment.student.full_name} ({payment.student.admission_number})",
        f"Fee head: {payment.fee_head.name}",
        f"Amount paid: {payment.amount}",
        f"Discount: {payment.discount}",
        f"Method: {payment.get_method_display()}",
        f"Date paid: {payment.paid_on:%d %b %Y}",
        f"Received by: {payment.received_by or '—'}",
    ]
    if payment.notes:
        lines.append(f"Notes: {payment.notes}")
    return _letter_pdf(
        "Fee Receipt",
        "OFFICIAL FEE RECEIPT",
        lines,
        author="Accounts Office",
        school_name=school_name,
    )