"""Communication services: placeholder rendering, recipient resolution,
queue enqueue, and gateway claim/report — all offline-first and best-effort.
"""

import datetime
import re

from django.utils import timezone

from .models import MessageTemplate, MessageBatch, Outbox, OutboxStatus

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def render_body(text, **context):
    """Replace {name} placeholders with values from context.

    Unknown or empty placeholders are left untouched so templates degrade
    gracefully when optional data (e.g. parent name) is missing.
    """

    def _replace(match):
        key = match.group(1)
        value = context.get(key)
        if value is None:
            return match.group(0)
        return str(value)

    return _PLACEHOLDER_RE.sub(_replace, text)


def school_name():
    school = getattr(
        __import__("apps.school.models", fromlist=["SchoolProfile"]),
        "SchoolProfile",
        None,
    )
    if school is None:
        return None
    try:
        profile = school.objects.first()
        return profile.name if profile else None
    except Exception:
        return None


def student_context(student):
    """Build the placeholder context for a student record."""
    guardians = getattr(student, "guardians", None)
    parent_name = None
    parent_phone = None
    if guardians is not None:
        from apps.parents.models import Parent

        primary = guardians.filter(is_primary=True).first()
        guardian = primary or guardians.first()
        if guardian:
            parent_name = getattr(guardian, "full_name", None) or getattr(
                guardian, "name", None
            )
            parent_phone = getattr(guardian, "phone", "") or ""
    klass = getattr(student, "klass", None)
    return {
        "student_name": getattr(student, "full_name", ""),
        "full_name": getattr(student, "full_name", ""),
        "admission_number": getattr(student, "admission_number", ""),
        "roll_number": getattr(student, "roll_number", ""),
        "class_name": getattr(klass, "name", "") if klass else "",
        "class": getattr(klass, "name", "") if klass else "",
        "parent_name": parent_name or "",
        "guardian": parent_name or "",
        "school_name": school_name() or "",
        "date": datetime.date.today().strftime("%d %b %Y"),
    }


def recipient_for_parent(parent, student=None):
    return {
        "name": getattr(parent, "full_name", None) or getattr(parent, "name", ""),
        "phone": getattr(parent, "phone", "") or "",
        "student": student,
        "context": student_context(student) if student else {},
    }


def resolve_recipients(mode, klass=None, manual_text=""):
    """Return a list of recipient dicts.

    mode ∈ {"class", "all_students", "manual"}. Each dict:
    {"name", "phone", "student", "context"}.
    """
    from apps.students.models import Student

    recipients = []

    if mode == "manual":
        for line in (manual_text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if "," in line:
                name, phone = (part.strip() for part in line.split(",", 1))
            else:
                name, phone = "", line
            if phone:
                recipients.append({"name": name, "phone": phone, "student": None, "context": {}})
        return recipients

    queryset = Student.objects.exclude(status="left")
    if mode == "class" and klass:
        queryset = queryset.filter(klass=klass)

    for student in queryset.exclude(phone="").filter(phone__isnull=False):
        recipients.append(
            {
                "name": student.full_name,
                "phone": student.phone,
                "student": student,
                "context": student_context(student),
            }
        )
        guard = parent_recipient(student)
        if guard and guard["phone"]:
            recipients.append(guard)
    return recipients


def parent_recipient(student):
    guardians = getattr(student, "guardians", None)
    if not guardians:
        return None
    from apps.parents.models import Parent

    primary = guardians.filter(is_primary=True).first()
    guardian = primary or guardians.first()
    if not guardian or not getattr(guardian, "phone", ""):
        return None
    return recipient_for_parent(guardian, student)


def _number(value):
    """Extract phone digits; returns '' when missing."""
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def enqueue_messages(recipients, body_text, template=None, channel="sms",
                     priority="normal", scheduled_for=None, batch=None):
    """Create Outbox rows for a resolved recipient list. Best-effort: rows
    without a usable number are skipped. Returns the created count."""
    created = 0
    for recipient in recipients:
        number = _number(recipient.get("phone"))
        if not number:
            continue
        context = recipient.get("context") or {}
        body = render_body(body_text, **context)
        Outbox.objects.create(
            batch=batch,
            template=template,
            template_key=template.key if template else "",
            recipient=number,
            phone=number,
            to_number=number,
            student=recipient.get("student"),
            channel=channel,
            priority=priority,
            message=body,
            body=body,
            status=OutboxStatus.SCHEDULED if scheduled_for else OutboxStatus.PENDING,
            scheduled_for=scheduled_for,
        )
        created += 1
    return created


def retry_message(outbox):
    if outbox.status == OutboxStatus.CANCELLED:
        return False
    outbox.status = OutboxStatus.PENDING
    outbox.scheduled_for = None
    outbox.failure_reason = ""
    outbox.save(update_fields=["status", "scheduled_for", "failure_reason"])
    return True


def claim_due(limit=50):
    """Claim messages that are due, returning a list for the gateway."""
    due = []
    for outbox in Outbox.objects.filter(status__in=[OutboxStatus.PENDING, OutboxStatus.SCHEDULED])[:limit]:
        if not outbox.is_due:
            continue
        outbox.status = OutboxStatus.PROCESSING
        outbox.attempt_count += 1
        outbox.save(update_fields=["status", "attempt_count"])
        due.append(outbox)
    return due


def report_results(report_rows):
    """Apply gateway send reports. report_rows: [{id, status, error?, gateway?}]"""
    updated = {"sent": 0, "failed": 0, "unknown": 0}
    for row in report_rows:
        try:
            outbox = Outbox.objects.get(pk=row.get("id"))
        except Outbox.DoesNotExist:
            updated["unknown"] += 1
            continue
        status = row.get("status")
        if status in (OutboxStatus.SENT, "delivered"):
            outbox.status = OutboxStatus.SENT
            outbox.sent_at = timezone.now()
            outbox.failure_reason = ""
            if row.get("gateway"):
                outbox.gateway = row.get("gateway")
            outbox.save(update_fields=["status", "sent_at", "failure_reason", "gateway"])
            updated["sent"] += 1
        elif status in (OutboxStatus.FAILED, "error"):
            outbox.status = OutboxStatus.FAILED
            outbox.failure_reason = row.get("error", "")[:2000]
            outbox.save(update_fields=["status", "failure_reason"])
            updated["failed"] += 1
    return updated


def autosend(limit=50):
    """Simulated gateway for dev/offline tests: send due messages at once."""
    claimed = claim_due(limit)
    sent = 0
    for outbox in claimed:
        outbox.status = OutboxStatus.SENT
        outbox.sent_at = timezone.now()
        outbox.gateway = "offline-simulator"
        outbox.save(update_fields=["status", "sent_at", "gateway"])
        sent += 1
    return len(claimed), sent


# Re-export for the gateway hook used by attendance.
def enqueue_student_message(template_key, student, message, **kwargs):
    try:
        template = MessageTemplate.objects.filter(key=template_key).first()
    except Exception:
        template = None
    number = _number(getattr(student, "phone", ""))
    if not number:
        return None
    valid_fields = {
        field.name
        for field in Outbox._meta.fields
    }
    payload = {
        "template": template,
        "template_key": template.key if template else template_key,
        "recipient": number,
        "phone": number,
        "to_number": number,
        "student": student,
        "channel": getattr(template, "channel", "sms") if template else "sms",
        "message": message,
        "body": message,
        "status": OutboxStatus.PENDING,
        "created_at": timezone.now(),
    }
    kwargs = {k: v for k, v in payload.items() if k in valid_fields}
    return Outbox.objects.create(**kwargs)


def enqueue_message(recipient, message, template=None, channel="sms",
                    priority="normal", scheduled_for=None, batch=None,
                    student=None):
    """Single-message convenience wrapper (used by hooks like the SMS
    gateway push)."""
    number = _number(recipient)
    if not number:
        return None
    return Outbox.objects.create(
        batch=batch,
        template=template,
        template_key=template.key if template else "",
        recipient=number,
        phone=number,
        to_number=number,
        student=student,
        channel=channel,
        priority=priority,
        message=message,
        body=message,
        status=OutboxStatus.SCHEDULED if scheduled_for else OutboxStatus.PENDING,
        scheduled_for=scheduled_for,
    )