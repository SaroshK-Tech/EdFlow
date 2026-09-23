from django.contrib import admin

from .models import Device, DeviceEvent


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "device_type",
        "status",
        "connection",
        "ip_address",
        "last_seen",
        "created_at",
    )
    list_filter = ("device_type", "status", "connection")
    search_fields = ("name", "model", "serial_number", "ip_address")


@admin.register(DeviceEvent)
class DeviceEventAdmin(admin.ModelAdmin):
    list_display = ("device", "event_type", "created_at")
    list_filter = ("event_type",)
    search_fields = ("device__name", "detail")