"""Attendance side-effects that must never block normal operation."""

import datetime

from django.utils import timezone

TEMPLATE_KEY = "student_absent"


def enqueue_absence_messages(student, period_info=None):
    """Best-effort offline SMS queue for an absent student.

    The communication app is optional; if its models are unavailable the call
    is silently skipped so attendance never fails because of messaging.
    """

    try:
        from apps.communication.models import Outbox
    except Exception:
        return None

    try:
        message = (
            f"Dear Parent, {student.full_name} ({student.admission_number}) "
            "was marked absent"
        )
        if period_info:
            message += f" in {period_info}"
        message += f" on {datetime.date.today():%d %b %Y}."
        valid_fields = {field.name for field in Outbox._meta.fields}
        payload = {
            "template_key": TEMPLATE_KEY,
            "recipient": student.phone,
            "phone": student.phone,
            "to_number": student.phone,
            "student": student,
            "message": message,
            "body": message,
            "status": "pending",
            "created_at": timezone.now(),
        }
        kwargs = {key: value for key, value in payload.items() if key in valid_fields}
        return Outbox.objects.create(**kwargs)
    except Exception:
        return None
