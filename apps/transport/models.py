from django.db import models
from django.utils import timezone


class VehicleStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    OUT_OF_SERVICE = "out_of_service", "Out of service"
    MAINTENANCE = "maintenance", "Maintenance"


class DriverStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class AssignmentDirection(models.TextChoices):
    TO_SCHOOL = "to_school", "To school"
    FROM_SCHOOL = "from_school", "From school"


class Vehicle(models.Model):
    """School-owned or contracted vehicle (spec §21)."""

    registration_number = models.CharField(max_length=50, unique=True)
    model = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=25, choices=VehicleStatus.choices, default=VehicleStatus.ACTIVE
    )
    owner = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["registration_number"]

    def __str__(self):
        return self.registration_number


class Driver(models.Model):
    """Transport driver with licence details."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    documents_note = models.TextField(blank=True)
    status = models.CharField(
        max_length=15, choices=DriverStatus.choices, default=DriverStatus.ACTIVE
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Route(models.Model):
    """Bus route served by a vehicle and a driver."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    vehicle = models.ForeignKey(
        Vehicle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="routes",
    )
    assigned_driver = models.ForeignKey(
        Driver,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="routes",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Stop(models.Model):
    """Pickup/drop-off point on a route."""

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=150)
    sequence = models.PositiveIntegerField(default=0)
    pickup_time = models.TimeField(null=True, blank=True)
    dropoff_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["route", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["route", "name"], name="unique_stop_name_per_route"),
        ]

    def __str__(self):
        return self.name


class TransportAssignment(models.Model):
    """Student allocated to a route/stop for a direction."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="transport_assignments",
    )
    route = models.ForeignKey(
        Route, on_delete=models.CASCADE, related_name="transport_assignments"
    )
    stop = models.ForeignKey(
        Stop,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transport_assignments",
    )
    direction = models.CharField(
        max_length=15,
        choices=AssignmentDirection.choices,
        default=AssignmentDirection.TO_SCHOOL,
    )
    transport_fee_per_term = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    is_active = models.BooleanField(default=True)
    active_from = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "direction"],
                name="unique_active_student_direction",
            ),
        ]

    def __str__(self):
        return f"{self.student.admission_number} → {self.route.name} ({self.get_direction_display()})"


class StaffAssignment(models.Model):
    """Staff allocated to a route/stop for a direction."""

    staff = models.ForeignKey(
        "staff.Staff",
        on_delete=models.CASCADE,
        related_name="transport_assignments",
    )
    route = models.ForeignKey(
        Route, on_delete=models.CASCADE, related_name="staff_assignments"
    )
    stop = models.ForeignKey(
        Stop,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_assignments",
    )
    direction = models.CharField(
        max_length=15,
        choices=AssignmentDirection.choices,
        default=AssignmentDirection.TO_SCHOOL,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.staff.employee_code} → {self.route.name} ({self.get_direction_display()})"