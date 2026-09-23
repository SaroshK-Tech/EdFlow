from django.conf import settings
from django.db import models
from django.utils import timezone


class Channel(models.TextChoices):
    SMS = "sms", "SMS"
    WHATSAPP = "whatsapp", "WhatsApp"


class Priority(models.TextChoices):
    HIGH = "high", "High"
    NORMAL = "normal", "Normal"
    LOW = "low", "Low"


class OutboxStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    SCHEDULED = "scheduled", "Scheduled"


class MessageTemplate(models.Model):
    """Configurable message template (spec §13)."""

    key = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.SMS
    )
    body = models.TextField(
        help_text="Use placeholders like {student_name}, {parent_name}, "
        "{class_name}, {school_name}, {date}."
    )
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(
        default=False, help_text="System templates cannot be deleted."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MessageBatch(models.Model):
    """A group of outbound messages created in one action."""

    subject = models.CharField(max_length=120)
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.SMS
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="message_batches",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Message Batches"

    def __str__(self):
        return f"{self.subject} ({self.created_at:%d %b %H:%M})"

    @property
    def recipient_count(self):
        return self.messages.count()

    @property
    def sent_count(self):
        return self.messages.filter(status=OutboxStatus.SENT).count()

    @property
    def failed_count(self):
        return self.messages.filter(status=OutboxStatus.FAILED).count()


class Outbox(models.Model):
    """Offline-first outbound message queue (spec §12).

    Every message is queued here with status and retry state. The local
    Android Communication Gateway pulls pending messages through the local
    API and reports back send status; optional providers never block normal
    school operation.
    """

    batch = models.ForeignKey(
        MessageBatch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    template = models.ForeignKey(
        MessageTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="outbox_messages",
    )
    template_key = models.CharField(max_length=64, blank=True)
    recipient = models.CharField(max_length=30)
    to_number = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    student = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="outbox_messages",
    )
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.SMS
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )
    message = models.TextField()
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=OutboxStatus.choices, default=OutboxStatus.PENDING
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    gateway = models.CharField(
        max_length=100, blank=True, help_text="Name of the gateway device that sent it."
    )
    server_message_id = models.CharField(
        max_length=64, blank=True, unique=True, null=True,
        help_text="Tracking id exchanged with the Android gateway.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.channel} → {self.recipient} ({self.status})"

    @property
    def is_due(self):
        return (
            self.status in (OutboxStatus.PENDING, OutboxStatus.SCHEDULED)
            and (self.scheduled_for is None or self.scheduled_for <= timezone.now())
        )