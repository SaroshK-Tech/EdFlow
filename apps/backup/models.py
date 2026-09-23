from django.conf import settings
from django.db import models
from django.utils import timezone


class BackupStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    VERIFYING = "verifying", "Verifying"


class BackupKind(models.TextChoices):
    MANUAL = "manual", "Manual"
    SCHEDULED = "scheduled", "Scheduled"
    PRE_RESTORE = "pre_restore", "Pre-restore safety"
    AUTOMATIC = "automatic", "Automatic"


class BackupProfile(models.Model):
    """Where backups live: local disk, USB/HDD drive letter or network share."""

    name = models.CharField(max_length=100)
    destination_path = models.CharField(
        max_length=500,
        help_text="Full folder path. Supports local disks, USB/external HDD "
        "drives (e.g. E:\\backups) and network shares (UNC paths, e.g. \\\\server\\edflow_backup).",
    )
    keep_count = models.PositiveIntegerField(
        default=5,
        help_text="Number of most recent backups to keep for this profile; "
        "older archives are deleted. 0 keeps everything.",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name


class BackupJob(models.Model):
    """A single backup run, its archive, checksum and verification state."""

    profile = models.ForeignKey(
        BackupProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
    kind = models.CharField(
        max_length=16, choices=BackupKind.choices, default=BackupKind.MANUAL
    )
    status = models.CharField(
        max_length=12, choices=BackupStatus.choices, default=BackupStatus.RUNNING
    )
    archive_name = models.CharField(max_length=255, blank=True)
    archive_path = models.CharField(max_length=600, blank=True)
    archive_size = models.BigIntegerField(default=0)
    checksum = models.CharField(
        max_length=64, blank=True, help_text="SHA-256 of the archive"
    )
    database_file = models.CharField(max_length=255, blank=True)
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    entries = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_jobs",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return self.archive_name or f"Backup #{self.pk}"

    @property
    def human_size(self):
        size = self.archive_size
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0

    def mark_running(self):
        self.status = BackupStatus.RUNNING
        self.save(update_fields=["status", "started_at"])

    def mark_success(self, **done):
        for field, value in done.items():
            setattr(self, field, value)
        self.status = BackupStatus.SUCCESS
        self.finished_at = timezone.now()
        self.save()

    def mark_failed(self, error):
        self.status = BackupStatus.FAILED
        self.error = str(error)[:4000]
        self.finished_at = timezone.now()
        self.save()