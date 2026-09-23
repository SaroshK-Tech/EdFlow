from django.contrib import admin

from .models import (
    Driver,
    Route,
    StaffAssignment,
    Stop,
    TransportAssignment,
    Vehicle,
)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "model", "capacity", "status", "owner")
    search_fields = ("registration_number", "model", "owner")


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "license_number", "license_expiry", "status")
    search_fields = ("name", "phone", "license_number")


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("name", "vehicle", "assigned_driver")
    search_fields = ("name",)


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ("route", "name", "sequence", "pickup_time", "dropoff_time")
    search_fields = ("name",)


@admin.register(TransportAssignment)
class TransportAssignmentAdmin(admin.ModelAdmin):
    list_display = ("student", "route", "stop", "direction", "is_active")
    list_filter = ("is_active", "direction")


@admin.register(StaffAssignment)
class StaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ("staff", "route", "stop", "direction", "active")
    list_filter = ("active", "direction")