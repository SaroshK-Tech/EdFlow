"""Integration helpers for discipline & behaviour (all guarded, never raise)."""


def _safe_create(model_class, **desired):
    field_names = {f.name for f in model_class._meta.get_fields()}
    payload = {k: v for k, v in desired.items() if k in field_names}
    return model_class.objects.create(**payload)


def notify_parent_for_incident(incident):
    """Enqueue an SMS to the guardian via the communication app, if present.

    Falls back silently when the communication app is not implemented yet so
    discipline workflows never break offline-first operation.
    """
    try:
        import apps.communication.models as comm
    except Exception:
        return False
    outbound = getattr(comm, "OutboundMessage", None)
    if outbound is None:
        return False
    try:
        _safe_create(
            outbound,
            student=incident.student,
            template_key="discipline_report",
            recipient_phone=incident.student.phone,
            incident_id=incident.pk,
            body=f"Discipline report: {incident.title}",
        )
        return True
    except Exception:
        return False


def send_emergency_announcement(title, message, user=None):
    """Broadcast a general announcement via the notifications app, if present."""
    try:
        import apps.notifications.models as notif
    except Exception:
        return False
    target = None
    for name in ("Announcement", "AnnouncementMessage", "Notification"):
        model = getattr(notif, name, None)
        if model is not None:
            target = model
            break
    if target is None:
        return False
    try:
        _safe_create(
            target,
            title=title,
            message=message,
            body=message,
            created_by=user,
            is_emergency=True,
        )
        return True
    except Exception:
        return False


def credit_house_points(student, achievement):
    """Credit house points when the student belongs to a house (guarded)."""
    try:
        from apps.houses.models import HousePoint
    except ImportError:
        return False
    if not getattr(student, "house_id", None):
        return False
    try:
        _safe_create(
            HousePoint,
            house=student.house,
            student=student,
            points=achievement.house_points,
            reason=f"Achievement: {achievement.title}",
        )
        return True
    except Exception:
        return False