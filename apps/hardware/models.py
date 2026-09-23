import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class DeviceType(models.TextChoices):
    GATEWAY = "gateway", "Android Communication Gateway"
    PRINTER = "printer", "Printer"
    SCANNER = "scanner", "Scanner"
    BIOMETRIC = "biometric", "Biometric / fingerprint reader"
    PROJECTOR = "projector", "Projector"
    DESKTOP = "desktop", "Desktop / workstation"
    OTHER = "other", "Other"


class DeviceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    OFFLINE = "offline", "Offline"
    MAINTENANCE = "maintenance", "In maintenance"
    RETIRED = "retired", "Retired"


class Connection(models.TextChoices):
    USB = "usb", "USB"
    LAN = "lan", "LAN / Ethernet"
    WLAN = "wlan", "Wi-Fi"
    BLUETOOTH = "bluetooth", "Bluetooth"
    ADB = "adb", "ADB / debug"


class Device(models.Model):
    """Hardware used by the school system, incl. Android Communication
    Gateways (spec §35). Heartbeats keep last_seen / health fresh."""

    name = models.CharField(max_length=120)
    device_type = models.CharField(
        max_length=10, choices=DeviceType.choices, default=DeviceType.GATEWAY
    )
    status = models.CharField(
        max_length=15, choices=DeviceStatus.choices, default=DeviceStatus.ACTIVE
    )
    connection = models.CharField(
        max_length=12, choices=Connection.choices, default=Connection.LAN
    )
    serial_number = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, blank=True)
    location = models.CharField(max_length=120, blank=True, help_text="e.g. ICT office")
    firmware_version = models.CharField(max_length=50, blank=True)

    # Gateway health (spec §35)
    sim_info = models.CharField(max_length=120, blank=True)
    network_status = models.CharField(max_length=120, blank=True)
    battery_level = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Battery %, gateway only"
    )

    gateway_token = models.CharField(
        max_length=64, blank=True, editable=False,
        help_text="Secret the Android app presents via X-Gateway-Token.",
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    installed_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()})"

    def save(self, *args, **kwargs):
        if not self.gateway_token:
            self.gateway_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_online(self):
        if self.last_seen is None:
            return False
        return (timezone.now() - self.last_seen).total_seconds() < 300


class DeviceEvent(models.Model):
    """Timeline of device heartbeats and events."""

    EVENT_TYPES = [
        ("registered", "Registered"),
        ("heartbeat", "Heartbeat"),
        ("sms_sent", "SMS sent"),
        ("sms_failed", "SMS failed"),
        ("result", "Message result"),
        ("error", "Error"),
    ]

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default="heartbeat")
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["device", "-created_at"])]

    def __str__(self):
        return f"{self.device}: {self.get_event_type_display()}"


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class MaintenanceRequest(models.Model):
    """Maintenance / support ticket for a device (spec §11 hardware support)."""

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="maintenance_requests"
    )
    ticket_number = models.CharField(max_length=30, unique=True, blank=True)
    issue_title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=10, choices=TicketPriority.choices, default=TicketPriority.MEDIUM
    )
    status = models.CharField(
        max_length=12, choices=TicketStatus.choices, default=TicketStatus.OPEN
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_tickets",
    )
    assigned_to = models.CharField(max_length=120, blank=True)
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket_number} — {self.issue_title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            super().save(*args, **kwargs)
            self.ticket_number = f"MNT-{self.created_at:%Y%m%d}-{self.pk:05d}"
            MaintenanceRequest.objects.filter(pk=self.pk).update(
                ticket_number=self.ticket_number
            )
        else:
            super().save(*args, **kwargs)