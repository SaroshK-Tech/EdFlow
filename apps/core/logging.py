"""Helpers to record audit log entries from request handlers."""

from apps.core.models import log_audit


def audit(request, action, object_type="", object_id=None, details=""):
    ip = None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    log_audit(
        user=getattr(request, "user", None),
        action=action,
        object_type=object_type,
        object_id=object_id,
        details=details,
        ip_address=ip,
    )