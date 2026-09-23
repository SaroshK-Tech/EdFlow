from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    """Immutable audit trail for important operations (spec §4, §27)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        who = self.user.username if self.user else "system"
        return f"{self.created_at:%Y-%m-%d %H:%M} {who} — {self.action}"


def log_audit(
    user=None,
    action="",
    object_type="",
    object_id=None,
    details="",
    ip_address=None,
):
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details,
            ip_address=ip_address,
        )
    except Exception:  # pragma: no cover - never break the request over logging
        return None