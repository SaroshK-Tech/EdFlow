from django.conf import settings
from django.db import models
from django.utils import timezone


class Audience(models.TextChoices):
    ALL = "all", "Everyone"
    STAFF = "staff", "Staff only"
    TEACHERS = "teachers", "Teachers only"
    CLASS = "class", "A specific class"


class Announcement(models.Model):
    """Admin/principal announcements broadcast to staff, teachers or a class.

    Implementing `send_emergency_announcement` from the discipline app is
    a first-class citizen: `title`, `message`, `body`, `created_by`,
    `is_emergency` are all real fields here.
    """

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    message = models.TextField(blank=True)
    audience = models.CharField(
        max_length=10, choices=Audience.choices, default=Audience.ALL
    )
    klass = models.ForeignKey(
        "academics.Class",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="announcements",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="announcements",
    )
    is_emergency = models.BooleanField(
        default=False, help_text="Emergency broadcasts are marked and can trigger SMS."
    )
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self):
        return self.title

    @property
    def content(self):
        return self.body or self.message or ""


class Notification(models.Model):
    """Per-user notification (fed to the topbar bell)."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    announcement = models.ForeignKey(
        Announcement,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    text = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=30, default="megaphone")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.recipient}: {self.text}"


class InboxMessage(models.Model):
    """Internal staff messaging (spec §25) — works fully offline."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)
    is_important = models.BooleanField(default=False)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["recipient", "-sent_at"])]

    def __str__(self):
        return f"{self.sender or 'System'} → {self.recipient}: {self.subject}"

    @property
    def is_read(self):
        return self.read_at is not None