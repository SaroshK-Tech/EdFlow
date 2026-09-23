"""Hardware side-effects: device heartbeat + gateway token verification."""

from django.utils import timezone

from .models import Device, DeviceEvent


def heartbeat(device, event_type="heartbeat", detail=""):
    """Record a heartbeat without ever raising (offline-safe)."""
    try:
        device.last_seen = timezone.now()
        device.save(update_fields=["last_seen", "updated_at"])
        DeviceEvent.objects.create(device=device, event_type=event_type, detail=detail[:2000])
        return True
    except Exception:
        return False


def find_by_token(token):
    if not token:
        return None
    try:
        return Device.objects.filter(gateway_token=token).first()
    except Exception:
        return None


def device_for_outbox(outbox):
    """Best-effort resolution of the gateway that should claim an Outbox row."""
    if not outbox:
        return None
    try:
        return Device.objects.filter(device_type="gateway", status="active").order_by("-last_seen").first()
    except Exception:
        return None